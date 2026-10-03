# Simple game in python

TOTAL_QUESTIONS = 4
PASS_PERCENT = 50

QUESTIONS = (
    ('1. What is the name of my youtube channel? ', 'tech with tim'),
    ('2. What is my age? ', '17'),
    ('3. What is my favourite sport? ', 'soccer'),
    ('4. What is my favourite food? ', 'pizza'),
)


def normalize_answer(raw):
    """Layer 1: input normalization.

    Any input (including non-strings and unstringifiable objects) is
    reduced to a comparable lowercase token; unparseable input becomes
    the empty token, which can never match an answer.
    """
    try:
        text = str(raw)
    except Exception:
        return ''
    return text.strip().lower()


def initial_state():
    """Layer 2: state advancement (state factory)."""
    return {'answered': 0, 'score': 0, 'status': 'playing'}


def advance(state, raw_answer):
    """Layer 2: advance the state by one (normalized) answer.

    Pure: returns a new state, never mutates the input. Duplicate
    actions on a finished game are ignored, so the score can never
    leave the range [0, TOTAL_QUESTIONS].
    """
    if state['status'] != 'playing' or state['answered'] >= TOTAL_QUESTIONS:
        return dict(state)
    correct = normalize_answer(raw_answer) == QUESTIONS[state['answered']][1]
    return {
        'answered': state['answered'] + 1,
        'score': min(state['score'] + (1 if correct else 0), TOTAL_QUESTIONS),
        'status': 'playing',
    }


def finish(state):
    """Layers 3+4: clamp the score and decide the natural exit outcome."""
    score = max(0, min(state['score'], TOTAL_QUESTIONS))
    percent = int((score / TOTAL_QUESTIONS) * 100)
    return {
        'answered': state['answered'],
        'score': score,
        'status': 'complete',
        'percent': percent,
        'outcome': 'passed' if percent >= PASS_PERCENT else 'failed',
    }


def play(ask=input, tell=print):
    """Run the quiz. Returns the finished state.

    The loop always terminates: it runs at most TOTAL_QUESTIONS rounds,
    and an exhausted input stream (EOFError) exits naturally with the
    score collected so far.
    """
    tell('Hi, welcome to the Tim quiz!')
    tell('Try to get as many questions correct as possible...')

    state = initial_state()
    for prompt, _answer in QUESTIONS:
        try:
            raw = ask(prompt)
        except EOFError:
            break
        next_state = advance(state, raw)
        tell('Correct!' if next_state['score'] > state['score'] else 'Incorrect')
        state = next_state

    final = finish(state)
    tell('Thank you for playing, you got ' + str(final['score']) + ' questions correct!')
    tell('Mark: ' + str(final['percent']) + '%')
    tell('Nice! You passed!' if final['outcome'] == 'passed' else 'Better luck next time')
    return final


if __name__ == '__main__':
    play()
