"""Read native histories without modifying them; share Markdown by project."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from texts import t

HERE = Path(__file__).resolve().parent
USER = Path(os.path.expanduser('~'))
CODEX = Path(os.environ.get('CODEX_HOME', str(USER / '.codex')))
CLAUDE = USER / '.claude' / 'projects'
STORE = HERE / 'session-memory'
LABELS = {'claude': 'Claude Code', 'codex': 'Codex'}


def canonical(path):
    return os.path.normcase(os.path.abspath(path)).replace('\\', '/').casefold().removeprefix('//?/')


def folder_for(path):
    return STORE / hashlib.sha256(canonical(path).encode()).hexdigest()[:20]


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)


def records(path):
    try:
        with Path(path).open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield value
                except ValueError:
                    continue
    except OSError:
        return


def plain(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get('type') in ('text', 'input_text', 'output_text'):
            parts.append(part.get('text', ''))
        elif part.get('type') in ('image', 'input_image', 'localImage'):
            parts.append(t('md_image') + part.get('path', t('md_image_origin')) + ']')
    return '\n'.join(parts)


def human_text(text):
    text = re.sub(r'(?s)<system-reminder>.*?</system-reminder>', '', text)
    return text.strip()


def read_db(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
    db.row_factory = sqlite3.Row
    return db


def sessions(project):
    found = {}
    slug = re.sub(r'[^A-Za-z0-9]', '-', str(project))
    for file in (CLAUDE / slug).glob('*.jsonl'):
        try:
            stamp = file.stat().st_mtime
        except OSError:
            continue
        entry = {'id': file.stem, 'provider': 'claude', 'when': stamp,
                 'file': str(file), 'project': str(project), 'said': ''}
        # Validate cwd where available: non-Latin paths can share a slug.
        cwd = next((r.get('cwd') for r in records(file) if r.get('cwd')), None)
        if cwd and canonical(cwd) != canonical(project):
            continue
        found[('claude', file.stem)] = entry
    # Current Codex stores previews and cwd in SQLite (including paginated threads).
    for file in sorted(CODEX.glob('state_*.sqlite'), reverse=True):
        try:
            with read_db(file) as db:
                rows = db.execute('SELECT * FROM threads WHERE archived = 0').fetchall()
            for row in rows:
                if canonical(row['cwd']) != canonical(project):
                    continue
                if 'agent_path' in row.keys() and row['agent_path'] not in (None, '', '/root'):
                    continue
                entry = {'id': row['id'], 'provider': 'codex', 'when': row['updated_at'],
                         'file': row['rollout_path'], 'project': str(project),
                         'said': row['title'] or row['first_user_message']}
                found[('codex', entry['id'])] = entry
            break
        except (sqlite3.Error, OSError):
            continue
    # Legacy files are a fallback, and cover not-yet-indexed sessions.
    for file in (CODEX / 'sessions').rglob('*.jsonl'):
        meta = next(records(file), {})
        data = meta.get('payload', {})
        if meta.get('type') != 'session_meta' or canonical(data.get('cwd', '.')) != canonical(project):
            continue
        sid = data.get('id') or data.get('session_id')
        if not sid or ('codex', sid) in found or isinstance(data.get('source'), dict):
            continue
        found[('codex', sid)] = {'id': sid, 'provider': 'codex', 'when': file.stat().st_mtime,
                               'file': str(file), 'project': str(project), 'said': ''}
    for file in folder_for(project).glob('*.json'):
        try:
            entry = json.loads(file.read_text(encoding='utf-8'))
            if canonical(entry['project']) != canonical(project):
                continue
            key = (entry['provider'], entry['id'])
            if key not in found or entry['when'] > found[key]['when']:
                found[key] = entry
        except (OSError, ValueError, KeyError):
            continue
    return sorted(found.values(), key=lambda item: item['when'], reverse=True)


def messages(session):
    if session.get('snapshot'):
        try:
            value = json.loads(Path(session['snapshot']).read_text(encoding='utf-8'))
            return value['messages']
        except (OSError, ValueError, KeyError):
            pass
    result = []
    if session['provider'] == 'codex':
        for file in sorted(CODEX.glob('thread_history_*.sqlite'), reverse=True):
            try:
                with read_db(file) as db:
                    rows = db.execute("SELECT item_json FROM thread_items WHERE thread_id=? "
                                      "AND item_type IN ('userMessage','agentMessage') "
                                      'ORDER BY rollout_ordinal', (session['id'],)).fetchall()
                for row in rows:
                    item = json.loads(row[0])
                    role = 'user' if item['type'] == 'userMessage' else 'assistant'
                    text = plain(item.get('content')) if role == 'user' else item.get('text', '')
                    if text:
                        result.append({'role': role, 'text': text})
                if result:
                    return result
            except (sqlite3.Error, OSError, ValueError):
                continue
    for entry in records(session.get('file', '')):
        if session['provider'] == 'claude':
            role = entry.get('type')
            if role not in ('user', 'assistant') or entry.get('isSidechain'):
                continue
            text = human_text(plain(entry.get('message', {}).get('content')))
        else:
            if entry.get('type') != 'response_item':
                continue
            item = entry.get('payload', {})
            role = item.get('role')
            if item.get('type') != 'message' or role not in ('user', 'assistant'):
                continue
            text = human_text(plain(item.get('content')))
            if text.startswith(('<environment_context>', '<permissions instructions>')):
                continue
        if text:
            result.append({'role': role, 'text': text})
    return result


def save(session, transcript=None):
    transcript = messages(session) if transcript is None else transcript
    if not transcript:
        return None
    entry = {k: v for k, v in session.items() if k != 'messages'}
    entry['said'] = next((m['text'] for m in reversed(transcript) if m['role'] == 'user'), '')[:500]
    stem = entry['provider'] + '-' + re.sub(r'[^A-Za-z0-9_-]', '_', entry['id'])
    base = folder_for(entry['project']) / stem
    entry['snapshot'] = str(base.with_suffix('.json'))
    entry['markdown'] = str(base.with_suffix('.md'))
    atomic_text(entry['snapshot'], json.dumps({**entry, 'messages': transcript}, ensure_ascii=False, indent=2))
    body = ['# ' + LABELS[entry['provider']] + ' — ' + entry['project'],
            '', t('md_session') + entry['id'], t('md_updated') + time.strftime('%d.%m.%Y %H:%M', time.localtime(entry['when'])), '']
    for item in transcript:
        body.extend(['## ' + (t('md_user') if item['role'] == 'user' else LABELS[entry['provider']]), '', item['text'], ''])
    atomic_text(entry['markdown'], '\n'.join(body))
    atomic_text(base.parent / 'MEMORY.md', t('md_memory').format(stem=stem, project=entry['project']))
    return entry


