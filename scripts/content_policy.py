"""Generated-only, single-use assets across channels; unknown provenance fails closed."""
import hashlib
from asset_library import read_json, identity


def profile(root):
    return read_json(root / 'data/channel_profile.json', {})


def enabled(root):
    settings=profile(root)
    return settings.get('generated_only') is True or settings.get('recording_based_mixes') is True


def approved_review(review):
    if not (review.get('approved') is True and review.get('status')=='approved'
            and review.get('notes') and review.get('reviewed_at')):
        return False
    if (review.get('approval_method')=='user_authorized_automatic'
            and review.get('approval_authorization')
            and review.get('quality',{}).get('technical_checked') is True):
        return True
    return all(review.get('quality',{}).get(k) is True for k in ('full_playback','loop_checked'))


def approved_recording_mix(root, asset):
    settings=profile(root)
    if not settings.get('recording_based_mixes') or not asset.get('sha256') or not asset.get('generator_sha256'):
        return False
    components=asset.get('components',[])
    recordings=[c for c in components if c.get('kind')=='licensed_recording']
    return bool(recordings and any(c.get('kind')=='procedural' for c in components)
        and all(c.get('kind') in {'procedural','licensed_recording'} for c in components)
        and all(c.get('profile',{}).get('source') in (None,'651189') for c in components if c.get('kind')=='procedural')
        and all(str(c.get('id')) in settings.get('allowed_recording_sources',{})
            and c.get('source_sha256')==settings['allowed_recording_sources'][str(c.get('id'))]
            and c.get('license','').rstrip('/') in {'http://creativecommons.org/publicdomain/zero/1.0','https://creativecommons.org/publicdomain/zero/1.0'} for c in recordings))


def tokens(asset, kind, shared_recording=False):
    result = {identity(asset, kind)}
    for value in (asset.get('sha256'), asset.get('custom_scene', {}).get('master_sha256')):
        if value:
            result.add('sha256:' + value)
    for component in asset.get('components', []):
        if component.get('source_sha256') and not shared_recording:
            result.add('sha256:' + component['source_sha256'])
        if component.get('kind') == 'procedural' and component.get('seed') is not None:
            result.add('procedural:' + str(component['seed']) + ':' + str(asset.get('generator_sha256')))
    return result


def generated(asset, kind):
    if not asset.get('sha256'):
        return False
    if kind == 'video':
        return bool(asset.get('generator') == 'built-in image_gen'
                    and asset.get('custom_scene', {}).get('master_sha256')
                    and asset.get('pexels_id') is None)
    components = asset.get('components')
    return bool(asset.get('generator_sha256') and components and all(
        c.get('kind') == 'procedural' and c.get('seed') is not None
        and c.get('method') and not c.get('profile', {}).get('source')
        for c in components))


def exclusion_tokens(root, entries):
    # This snapshot is mandatory: deleting a channel or clearing the live ledger
    # must never clear migration exclusions.
    snapshot = read_json(root / 'data/content_exclusions.json', None)
    if not isinstance(snapshot, dict) or snapshot.get('version') != 1:
        raise RuntimeError('Required content exclusion snapshot is missing or invalid')
    used = {kind: set(snapshot[kind]) for kind in ('video', 'audio')}
    for entry in entries.values():
        for kind in used:
            used[kind].update(tokens(entry['assets'][kind], kind, shared_recording=kind=='audio' and profile(root).get('recording_based_mixes') is True))
    return used


def allowed(root, asset, kind, used, check_file=False):
    shared=kind=='audio' and approved_recording_mix(root,asset)
    if not (generated(asset, kind) or shared) or tokens(asset, kind, shared_recording=shared) & used[kind]:
        return False
    if check_file:
        relative = asset.get('local_path') if kind == 'video' else asset.get('path') or 'audio/' + asset['filename']
        path = (root / relative).resolve()
        path.relative_to(root.resolve())
        if not path.is_file():
            return False
        with path.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != asset['sha256']:
                return False
    return True


def check_assets(root, assets, entries):
    if not enabled(root):
        return
    settings = profile(root)
    if assets.get('channel_id') != settings['youtube_channel_id']:
        raise RuntimeError('Assets belong to a different channel; generate a new selection')
    if assets.get('selection_explanation', {}).get('policy') != 'channel_profile':
        raise RuntimeError('Generated-only channel requires channel selection; legacy overrides cannot publish')
    used = exclusion_tokens(root, entries)
    for kind in ('video', 'audio'):
        if not allowed(root, assets[kind], kind, used, check_file=True):
            raise RuntimeError(f'{kind} is previously used, externally sourced, unverified, or changed on disk')
        review = assets[kind].get('review', {})
        prior_visual = kind=='video' and review.get('approved') is True and any(
            r.get('status')=='approve' and r.get('package_checked') is True
            and r.get('preview_sha256')==assets[kind].get('sha256')
            for r in read_json(root/'data/three_week_review_decisions.json',{}).get('videos',[]))
        if not approved_review(review) and not prior_visual:
            raise RuntimeError(f'{kind} requires dated full-playback and loop approval')


def check_history_audit(root):
    if enabled(root) and profile(root).get('history_reconciled') is not True:
        raise RuntimeError('Publishing paused: reconcile both channels, including private/scheduled uploads, before activation')


def check_resume(root, entry):
    if enabled(root) and (entry.get('channel_id') or entry['assets'].get('channel_id')) != profile(root)['youtube_channel_id']:
        raise RuntimeError('Cannot resume an old-channel or unidentified upload on the new channel')
