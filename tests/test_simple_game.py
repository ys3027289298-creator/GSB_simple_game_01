"""Exhaustive short-input-sequence tests for simpleGame.

Every sequence of up to 4 scripted inputs drawn from a mixed alphabet
(correct answers, case/whitespace variants, wrong answers, empty input,
and EOF markers) is played through `simpleGame.play`. Each path's final
state is asserted to be a definite success/failure terminal state and is
recorded to tests/path_states.jsonl for auditing.
"""
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import simpleGame

EXPECTED_ANSWERS = [answer for _prompt, answer in simpleGame.QUESTIONS]
EXPECTED_PROMPTS = [prompt for prompt, _answer in simpleGame.QUESTIONS]
EXPECTED_BANNER = [
    'Hi, welcome to the Tim quiz!',
    'Try to get as many questions correct as possible...',
]
EOF_MARKER = None

# Mixed alphabet: canonical answers, case/whitespace variants, wrong
# answers, numeric-looking input, empty input, and end-of-stream.
ALPHABET = [
    'tech with tim',
    'TECH WITH TIM',
    '  soccer  ',
    'PiZzA',
    '17',
    'wrong answer',
    '',
    EOF_MARKER,
]
EXTRA_ALPHABET = ['tech with tim', '17', EOF_MARKER]

TERMINAL_LINES = ('Nice! You passed!', 'Better luck next time')


def short_sequences():
    cases = []
    for length in range(5):
        cases.extend(itertools.product(ALPHABET, repeat=length))
    for combo in itertools.product(EXTRA_ALPHABET, repeat=5):
        cases.append(combo)
    return cases


SEQUENCES = short_sequences()


def make_ask(scripted, prompts):
    queue = list(scripted)

    def ask(prompt):
        prompts.append(prompt)
        if not queue:
            raise EOFError  # input stream exhausted
        item = queue.pop(0)
        if item is EOF_MARKER:
            raise EOFError
        return item

    ask.queue = queue
    return ask


def oracle_score(scripted):
    """Independent reference implementation for the expected score.

    Returns (score, answered, consumed, eof): how many scripted items
    were popped and whether an explicit EOF marker ended the quiz.
    """
    score = 0
    answered = 0
    consumed = 0
    eof = False
    for raw in scripted:
        if answered >= simpleGame.TOTAL_QUESTIONS:
            break
        consumed += 1
        if raw is EOF_MARKER:
            eof = True
            break
        try:
            token = str(raw).strip().lower()
        except Exception:
            token = ''
        if token == EXPECTED_ANSWERS[answered]:
            score += 1
        answered += 1
    return score, answered, consumed, eof


@pytest.fixture(scope='session')
def path_state_log():
    path = Path(__file__).with_name('path_states.jsonl')
    handle = path.open('w', encoding='utf-8')
    yield handle
    handle.close()


@pytest.fixture
def record_path(path_state_log, request):
    def record(payload):
        path_state_log.write(
            json.dumps({'case': request.node.callspec.id, **payload}, default=repr)
            + '\n'
        )

    return record


@pytest.mark.parametrize('scripted', SEQUENCES, ids=[f'seq{i}' for i in range(len(SEQUENCES))])
def test_every_short_sequence_reaches_a_terminal_state(scripted, record_path):
    prompts, output = [], []
    ask = make_ask(scripted, prompts)
    final = simpleGame.play(ask=ask, tell=output.append)

    expected_score, expected_answered, consumed, eof = oracle_score(scripted)
    expected_percent = int((expected_score / simpleGame.TOTAL_QUESTIONS) * 100)
    expected_outcome = 'passed' if expected_percent >= simpleGame.PASS_PERCENT else 'failed'

    # Termination: every path ends in a definite success/failure state.
    assert final['status'] == 'complete'
    assert final['outcome'] in ('passed', 'failed')
    assert output[-1] in TERMINAL_LINES

    # Score stays within bounds and matches the independent oracle.
    assert 0 <= final['score'] <= simpleGame.TOTAL_QUESTIONS
    assert final['score'] == expected_score
    assert final['answered'] == expected_answered
    assert final['percent'] == expected_percent
    assert final['outcome'] == expected_outcome

    # Prompts and per-question feedback are emitted in order, unchanged.
    # input(prompt) displays the prompt even when the stream then hits EOF.
    assert output[:2] == EXPECTED_BANNER
    prompt_count = expected_answered + (
        1 if expected_answered < simpleGame.TOTAL_QUESTIONS else 0
    )
    assert prompts == EXPECTED_PROMPTS[:prompt_count]
    feedback = output[2:2 + expected_answered]
    assert set(feedback) <= {'Correct!', 'Incorrect'}

    # Closing text uses the exact original wording.
    assert output[-3] == (
        'Thank you for playing, you got ' + str(expected_score) + ' questions correct!'
    )
    assert output[-2] == 'Mark: ' + str(expected_percent) + '%'
    assert output[-1] == (
        'Nice! You passed!' if expected_outcome == 'passed' else 'Better luck next time'
    )

    # Inputs beyond the 4 questions are never consumed (no state pollution).
    assert len(ask.queue) == len(scripted) - consumed

    record_path({
        'inputs': list(scripted),
        'final_state': final,
        'prompts': prompts,
        'output': output,
    })


@pytest.mark.parametrize(
    'scripted',
    [
        pytest.param(['tech with tim'] * 8, id='repeat-correct-8x'),
        pytest.param(['TECH WITH TIM', '17', 'SOCCER', 'PIZZA', 'pizza', 'extra'], id='mixed-case-extra'),
        pytest.param([None, 17, b'soccer', 'pizza'], id='non-string-inputs'),
        pytest.param([17, 17, 17, 17], id='numeric-inputs'),
        pytest.param(['', '', '', ''], id='empty-inputs'),
        pytest.param(['x'] * 10, id='wrong-10x'),
        pytest.param(['tech with tim', '17', EOF_MARKER, 'soccer', 'pizza'], id='eof-mid-quiz'),
        pytest.param(['  tech with tim  ', ' 17 ', ' soccer ', ' pizza '], id='whitespace-padded'),
    ],
)
def test_representative_long_and_odd_sequences(scripted, record_path):
    prompts, output = [], []
    final = simpleGame.play(ask=make_ask(scripted, prompts), tell=output.append)

    expected_score, expected_answered, _consumed, _eof = oracle_score(scripted)
    assert final['status'] == 'complete'
    assert final['outcome'] in ('passed', 'failed')
    assert output[-1] in TERMINAL_LINES
    assert final['score'] == expected_score
    assert final['answered'] == expected_answered
    assert 0 <= final['score'] <= simpleGame.TOTAL_QUESTIONS

    record_path({'inputs': list(scripted), 'final_state': final, 'output': output})


def test_unstringifiable_input_is_a_safe_wrong_answer():
    class Unstringifiable:
        def __str__(self):
            raise RuntimeError('boom')

    scripted = [Unstringifiable(), '17', 'soccer', 'pizza']
    output = []
    final = simpleGame.play(ask=make_ask(scripted, []), tell=output.append)
    assert final['score'] == 3
    assert final['outcome'] == 'passed'
    assert output[2] == 'Incorrect'


def test_advance_ignores_duplicate_actions_after_completion():
    state = {'answered': simpleGame.TOTAL_QUESTIONS, 'score': 4, 'status': 'complete'}
    assert simpleGame.advance(state, 'pizza') == state
    assert state == {'answered': simpleGame.TOTAL_QUESTIONS, 'score': 4, 'status': 'complete'}


def test_advance_never_mutates_the_passed_state():
    state = simpleGame.initial_state()
    snapshot = dict(state)
    simpleGame.advance(state, 'tech with tim')
    assert state == snapshot


def test_finish_clamps_out_of_bounds_scores():
    high = simpleGame.finish({'answered': 4, 'score': 99, 'status': 'playing'})
    low = simpleGame.finish({'answered': 4, 'score': -3, 'status': 'playing'})
    assert high['score'] == simpleGame.TOTAL_QUESTIONS
    assert high['percent'] == 100
    assert high['outcome'] == 'passed'
    assert low['score'] == 0
    assert low['percent'] == 0
    assert low['outcome'] == 'failed'


def test_play_does_not_touch_module_level_state():
    before = {
        name: (tuple(value) if isinstance(value, tuple) else value)
        for name, value in vars(simpleGame).items()
        if not name.startswith('__')
    }
    prompts, output = [], []
    simpleGame.play(ask=make_ask(['tech with tim', '17', 'soccer', 'pizza'], prompts),
                    tell=output.append)
    after = {
        name: (tuple(value) if isinstance(value, tuple) else value)
        for name, value in vars(simpleGame).items()
        if not name.startswith('__')
    }
    assert after == before


def test_cli_exits_cleanly_on_eof():
    result = subprocess.run(
        [sys.executable, 'simpleGame.py'],
        cwd=Path(__file__).resolve().parent.parent,
        input='',
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines()[-1] in TERMINAL_LINES


def test_cli_perfect_run_passes():
    result = subprocess.run(
        [sys.executable, 'simpleGame.py'],
        cwd=Path(__file__).resolve().parent.parent,
        input='Tech With Tim\n17\nSoccer\nPizza\n',
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines()[-1] == 'Nice! You passed!'
