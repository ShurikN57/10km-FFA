"""Résout une demande de collecte GitHub (bouton ou fichier versionné)."""
import json
import os
from pathlib import Path
import re
from datetime import datetime

from collect_ffa import current_season


def resolve_request(event, inputs, document=None):
    if event == 'push':
        if not isinstance(document, dict):
            raise ValueError('Une demande JSON est requise pour un lancement par commit.')
        if not document.get('requested_at'):
            raise ValueError('La demande doit porter une date requested_at.')
        stamp = datetime.fromisoformat(document['requested_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('requested_at doit préciser son fuseau horaire.')
        values = document
    elif event == 'workflow_dispatch':
        values = inputs
    elif event == 'pull_request':
        values = {}  # Un essai de PR ne déclenche jamais une collecte complète.
    else:
        raise ValueError('Événement de collecte non pris en charge.')
    season = str(values.get('season') or current_season())
    mode = values.get('mode') or 'probe'
    resume = str(values.get('resume_run') or '')
    if not re.fullmatch(r'[1-9][0-9]{3}', season):
        raise ValueError('Saison FFA attendue sur quatre chiffres.')
    if mode not in ('probe', 'full'):
        raise ValueError('Mode de collecte invalide.')
    if resume and not re.fullmatch(r'[1-9][0-9]*', resume):
        raise ValueError('resume_run doit être un ID GitHub numérique positif.')
    return {'season': season, 'mode': mode, 'resume_run': resume}


def main():
    event = os.environ['GITHUB_EVENT_NAME']
    document = None
    if event == 'push':
        document = json.loads(Path('data/collection-request.json').read_text(encoding='utf-8'))
    inputs = {'season': os.getenv('FFA_SEASON'), 'mode': os.getenv('FFA_MODE'),
              'resume_run': os.getenv('RESUME_RUN')}
    request = resolve_request(event, inputs, document)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for key, value in request.items():
            output.write(f'{key}={value}\n')
    print(f"Collecte demandée : saison {request['season']}, mode {request['mode']}, reprise {request['resume_run'] or 'non'}.")


if __name__ == '__main__':
    main()
