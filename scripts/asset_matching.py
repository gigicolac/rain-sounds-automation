"""Conservative matching: unknown labels never support specific claims."""
import re


def labels_for(asset):
    review = asset.get('review', {})
    return review.get('labels', {}) if review.get('approved') is True else {}


def compatible(audio, video):
    a, v = labels_for(audio), labels_for(video)
    for key in ('setting', 'intensity'):
        if a.get(key) and v.get(key) and a[key] != v[key]:
            return False
    return True


def title_allowed(title, audio, video):
    a, v = labels_for(audio), labels_for(video)
    text = title.lower()
    if any(term in text for term in ('no thunder', 'without thunder', 'thunder-free')):
        if a.get('thunder') is not False:
            return False
    elif 'thunder' in text and a.get('thunder') is not True:
        return False
    if 'pure rain' in text and not all(a.get(k) is False for k in ('thunder', 'traffic', 'animals', 'music', 'voices')):
        return False
    for word, value in (('heavy', 'heavy'), ('gentle', 'gentle'), ('light', 'gentle')):
        if re.search(r'\b' + word + r'\b', text) and a.get('intensity') != value:
            return False
    for setting in ('forest', 'city', 'roof', 'window', 'tent', 'lake'):
        if re.search(r'\b' + setting + r'\b', text) and (a.get('setting') != setting or v.get('setting') != setting):
            return False
    return True
