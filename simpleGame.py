# Simple game in python
#
# The game logic lives in four separated layers:
#   1. normalize_answer  -- input normalization (case, whitespace, non-strings)
#   2. new_state/advance -- pure state progression (no I/O, no globals)
#   3. clamp_score       -- score/index bounds guarding
#   4. play/main         -- I/O shell with a natural exit on end-of-input

TOTAL_QUESTIONS = 4
PASS_MARK = 50

QUESTIONS = (
    ('1. What is the name of my youtube channel? ', 'tech with tim'),
    ('2. What is my age? ', '17'),
    ('3. What is my favourite sport? ', 'soccer'),
    ('4. What is my favourite food? ', 'pizza'),
)

STATUS_PASS = 'pass'
STATUS_FAIL = 'fail'


def clamp_score(value):
    return max(0, min(TOTAL_QUESTIONS, value))


def normalize_answer(raw):
    if raw is None:
        return ''
    if not isinstance(raw, str):
        raw = str(raw)
    return ' '.join(raw.split()).casefold()


def new_state():
    return {'index': 0, 'score': 0, 'finished': False}


def advance(state, raw_answer):
    # Returns a NEW state dict; the input state is never mutated, so a
    # repeated/duplicate call can never corrupt or double-count progress.
    index = max(0, min(len(QUESTIONS), state['index']))
    score = clamp_score(state['score'])
    if index >= len(QUESTIONS):
        return {'index': index, 'score': score, 'finished': True}
    correct = normalize_answer(raw_answer) == normalize_answer(QUESTIONS[index][1])
    if correct:
        score = clamp_score(score + 1)
    index += 1
    return {'index': index, 'score': score, 'finished': index >= len(QUESTIONS)}


def result_status(state):
    percent = (clamp_score(state['score']) / TOTAL_QUESTIONS) * 100
    return STATUS_PASS if percent >= PASS_MARK else STATUS_FAIL


def play(input_func=None):
    if input_func is None:
        input_func = input
    print('Hi, welcome to the Tim quiz!')
    print('Try to get as many questions correct as possible...')

    state = new_state()

    for prompt, expected in QUESTIONS:
        try:
            ans = input_func(prompt)
        except EOFError:
            # Natural exit: the input stream ended early, so the remaining
            # questions are scored as incorrect and the game still settles.
            break
        if normalize_answer(ans) == normalize_answer(expected):
            print('Correct!')
        else:
            print('Incorrect')
        state = advance(state, ans)

    # End-of-input also settles the pure state machine, so every path
    # reaches a finished state with a bounded score.
    while not state['finished']:
        state = advance(state, '')
    score = state['score']
    totalQuestions = TOTAL_QUESTIONS

    print("Thank you for playing, you got " + str(score) + ' questions correct!')
    percent = (score / totalQuestions) * 100
    print("Mark: " + str(int(percent)) + '%')

    if percent >= 50:
        print('Nice! You passed!')
    else:
        print('Better luck next time')

    return state


def main():
    return play()


if __name__ == '__main__':
    main()
