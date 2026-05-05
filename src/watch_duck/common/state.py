def encode_state(state):
    return {
        'complete': 0,
        'queued': 1,
        'active': 2,
        'aborted': 3,
        'suspended': 4,
        'submitted': 5,
    }[state]


def decode_state(state):
    return {
        -1: 'unknown',
        0: 'complete',
        1: 'queued',
        2: 'active',
        3: 'aborted',
        4: 'suspended',
        5: 'submitted',
    }[state]
