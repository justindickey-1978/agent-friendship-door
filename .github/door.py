"""Opens the door once: checks the secret word in a new "I'm in" issue, then adds its author to
the private agent-friendship repo, records the name, deletes the issue and disables this workflow.

The door opens that one repo and nothing else. A collaborator on a personal repo always gets write
access, so anything Justin shares read-only (the food brain) is set up separately, by hand.

All issue content is untrusted and arrives through environment variables, never through the
workflow template. Wrong words get a short reply and a closed issue.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys

PRIVATE = 'justindickey-1978/agent-friendship'
DOOR = os.environ['REPO']
NUMBER = os.environ['NUMBER']
AUTHOR = os.environ['AUTHOR']


def field(body, label):
    m = re.search(r'^###\s*' + re.escape(label) + r'[^\n]*\n+(.*?)(?=\n###|\Z)', body or '', re.S | re.M)
    value = (m.group(1).strip() if m else '')
    return '' if value == '_No response_' else value


def normalize(word):
    return ' '.join(word.lower().split())


def gh(token, *args, data=None):
    env = {**os.environ, 'GH_TOKEN': token}
    r = subprocess.run(['gh', *args], env=env, input=json.dumps(data) if data is not None else None,
                       text=True, capture_output=True)
    if r.returncode:
        print(r.stderr, file=sys.stderr)
    return r


def main():
    body = os.environ.get('BODY', '')
    actions_token, door_token = os.environ['ACTIONS_TOKEN'], os.environ.get('DOOR_TOKEN', '')
    word = normalize(field(body, 'The secret word from the card'))
    expected = os.environ.get('WORD_SHA', '').strip().lower()
    if not expected or not hmac.compare_digest(hashlib.sha256(word.encode()).hexdigest(), expected):
        gh(actions_token, 'issue', 'comment', NUMBER, '-R', DOOR, '-b', "That's not the word on the card.")
        gh(actions_token, 'issue', 'close', NUMBER, '-R', DOOR)
        return
    if not door_token:
        sys.exit('DOOR_TOKEN is not set')

    r = gh(door_token, 'api', '-X', 'PUT', f'repos/{PRIVATE}/collaborators/{AUTHOR}', '-f', 'permission=push')
    if r.returncode:
        sys.exit('Could not add the collaborator')

    agent = re.sub(r"[^A-Za-z0-9 ._'-]", '', field(body, 'What should Edmund call your agent?'))[:40].strip()
    r = gh(door_token, 'api', f'repos/{PRIVATE}/contents/README.md')
    if not r.returncode:
        doc = json.loads(r.stdout)
        text = base64.b64decode(doc['content']).decode()
        text = text.replace('| Tim | Human.', f'| Tim (@{AUTHOR}) | Human.')
        if agent:
            text = text.replace("| Tim's agent | Tim's agent. Name to come. |", f"| {agent} | Tim's agent. |")
        gh(door_token, 'api', '-X', 'PUT', f'repos/{PRIVATE}/contents/README.md', '--input', '-', data={
            'message': f"Record Tim's acceptance (@{AUTHOR})\n\nAgent: door (for Justin)",
            'content': base64.b64encode(text.encode()).decode(),
            'sha': doc['sha'],
        })

    gh(door_token, 'api', 'graphql', '-f', 'query=mutation($id:ID!){deleteIssue(input:{issueId:$id}){clientMutationId}}',
       '-f', f"id={os.environ['NODE_ID']}")
    gh(actions_token, 'workflow', 'disable', 'door.yml', '-R', DOOR)


if __name__ == '__main__':
    main()
