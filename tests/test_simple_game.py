"""Parameterized tests for simpleGame.

Exhaustively plays every short input sequence (length 0..4 over a
5-token alphabet per question: exact-correct, case/whitespace variant,
wrong, empty, end-of-input), records the final state of each path to a
JSONL artifact, and asserts that every path reaches a definite
pass/fail terminal state without polluting module-level globals.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import hashlib
import io
import itertools
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import simpleGame

RECORDS_PATH = os.environ.get(
    'SIMPLE_GAME_PATH_RECORDS',
    os.path.join(os.path.dirname(__file__), '.path_records.jsonl'),
)

# Token alphabet per question:
#   'C' exact correct answer
#   'c' correct answer with different case / surrounding whitespace
#   'w' a wrong answer
#   'e' empty answer
#   'x' end-of-input (EOF) -- always terminal, nothing after it is read
TOKENS = ('C', 'c', 'w', 'e', 'x')

CASE_VARIANTS = {
    0: '  TeCh WiTh TiM\t',
    1: '  17  ',
    2: '\tSoCcEr ',
    3: ' PIZZA  ',
}


def token_input(token, question_index):
    if token == 'C':
        return simpleGame.QUESTIONS[question_index][1]
    if token == 'c':
        return CASE_VARIANTS[question_index]
    if token == 'w':
        return 'definitely wrong'
    if token == 'e':
        return ''
    raise ValueError(token)


def expand_tokens(tokens):
    """Turn a token string into the concrete input list (may be short)."""
    values = []
    for index, token in enumerate(tokens):
        if token == 'x':
            break
        values.append(token_input(token, index))
    return values


class FakeInput:
    """Stands in for builtins.input: echoes the prompt like the real one."""

    def __init__(self, values):
        self._values = list(values)
        self.prompts = []

    def __call__(self, prompt=''):
        self.prompts.append(prompt)
        print(prompt, end='')
        if not self._values:
            raise EOFError
        return self._values.pop(0)


def oracle(tokens):
    """Independent re-implementation of the expected game outcome."""
    values = expand_tokens(tokens)
    score = 0
    chunks = [
        'Hi, welcome to the Tim quiz!\n',
        'Try to get as many questions correct as possible...\n',
    ]
    prompts = []
    for index, (prompt, expected) in enumerate(simpleGame.QUESTIONS):
        prompts.append(prompt)
        chunks.append(prompt)
        if index >= len(values):
            break  # EOF: dangling prompt, remaining questions score 0
        if simpleGame.normalize_answer(values[index]) == simpleGame.normalize_answer(expected):
            score += 1
            chunks.append('Correct!\n')
        else:
            chunks.append('Incorrect\n')
    percent = (score / simpleGame.TOTAL_QUESTIONS) * 100
    chunks.append('Thank you for playing, you got ' + str(score) + ' questions correct!\n')
    chunks.append('Mark: ' + str(int(percent)) + '%\n')
    if percent >= 50:
        chunks.append('Nice! You passed!\n')
        status = simpleGame.STATUS_PASS
    else:
        chunks.append('Better luck next time\n')
        status = simpleGame.STATUS_FAIL
    return {
        'score': score,
        'status': status,
        'output': ''.join(chunks),
        'prompts': prompts,
    }


_module_globals_snapshot = None
_records_written = 0


def public_module_state():
    return {
        key: value
        for key, value in vars(simpleGame).items()
        if not key.startswith('__') and not callable(value)
    }


def run_game(tokens):
    """Play one path, return (final_state, captured_output, fake_input)."""
    values = expand_tokens(tokens)
    fake = FakeInput(values)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        state = simpleGame.play(input_func=fake)
    return state, buffer.getvalue(), fake


def record_path(tokens, state, output, globals_ok):
    global _records_written
    record = {
        'tokens': tokens,
        'inputs': expand_tokens(tokens),
        'answered': len(expand_tokens(tokens)),
        'index': state['index'],
        'score': state['score'],
        'finished': state['finished'],
        'status': simpleGame.result_status(state),
        'output_sha1': hashlib.sha1(output.encode()).hexdigest(),
        'globals_ok': globals_ok,
    }
    with open(RECORDS_PATH, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, sort_keys=True) + '\n')
    _records_written += 1


def setUpModule():
    if os.path.exists(RECORDS_PATH):
        os.remove(RECORDS_PATH)
    global _module_globals_snapshot
    _module_globals_snapshot = public_module_state()


def tearDownModule():
    with open(RECORDS_PATH, encoding='utf-8') as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    assert len(records) == _records_written, 'every played path must be recorded'
    for record in records:
        assert record['finished'] is True, record
        assert record['status'] in (simpleGame.STATUS_PASS, simpleGame.STATUS_FAIL), record
        assert 0 <= record['score'] <= simpleGame.TOTAL_QUESTIONS, record
        assert record['globals_ok'] is True, record
    assert public_module_state() == _module_globals_snapshot


class TestNormalizeAnswer(unittest.TestCase):
    def test_case_and_whitespace(self):
        self.assertEqual(simpleGame.normalize_answer('  TeCh WiTh   TiM\t'), 'tech with tim')
        self.assertEqual(simpleGame.normalize_answer('PIZZA'), 'pizza')
        self.assertEqual(simpleGame.normalize_answer(' 17 '), '17')

    def test_empty_and_none(self):
        self.assertEqual(simpleGame.normalize_answer(''), '')
        self.assertEqual(simpleGame.normalize_answer('   '), '')
        self.assertEqual(simpleGame.normalize_answer(None), '')

    def test_non_string_input_does_not_raise(self):
        self.assertEqual(simpleGame.normalize_answer(17), '17')
        self.assertEqual(simpleGame.normalize_answer(['pizza']), "['pizza']")


class TestStateMachine(unittest.TestCase):
    def test_new_state(self):
        self.assertEqual(simpleGame.new_state(),
                         {'index': 0, 'score': 0, 'finished': False})

    def test_advance_is_pure_and_repeatable(self):
        start = simpleGame.new_state()
        first = simpleGame.advance(start, 'Tech With Tim')
        again = simpleGame.advance(start, 'Tech With Tim')
        self.assertEqual(first, again)
        self.assertEqual(start, {'index': 0, 'score': 0, 'finished': False})
        self.assertEqual(first, {'index': 1, 'score': 1, 'finished': False})

    def test_advance_past_end_is_terminal_and_stable(self):
        state = {'index': simpleGame.TOTAL_QUESTIONS, 'score': 2, 'finished': True}
        self.assertEqual(simpleGame.advance(state, 'pizza'), state)
        self.assertEqual(simpleGame.advance(state, 'garbage'), state)

    def test_score_and_index_are_clamped(self):
        state = simpleGame.advance({'index': 0, 'score': 99, 'finished': False}, 'nope')
        self.assertLessEqual(state['score'], simpleGame.TOTAL_QUESTIONS)
        state = simpleGame.advance({'index': -3, 'score': -7, 'finished': False}, 'nope')
        self.assertGreaterEqual(state['index'], 0)
        self.assertGreaterEqual(state['score'], 0)

    def test_clamp_score(self):
        self.assertEqual(simpleGame.clamp_score(-1), 0)
        self.assertEqual(simpleGame.clamp_score(2), 2)
        self.assertEqual(simpleGame.clamp_score(99), simpleGame.TOTAL_QUESTIONS)

    def test_result_status_bounds(self):
        for score, expected in [(0, 'fail'), (1, 'fail'), (2, 'pass'),
                                (3, 'pass'), (4, 'pass'), (-5, 'fail'), (99, 'pass')]:
            with self.subTest(score=score):
                state = {'index': 4, 'score': score, 'finished': True}
                self.assertEqual(simpleGame.result_status(state), expected)


class TestExhaustiveShortPaths(unittest.TestCase):
    """Every input sequence of length 0..4 over TOKENS (1296 paths)."""

    def test_all_paths_terminate_with_expected_state(self):
        for length in range(0, simpleGame.TOTAL_QUESTIONS + 1):
            for combo in itertools.product(TOKENS, repeat=length):
                tokens = ''.join(combo)
                with self.subTest(tokens=tokens):
                    expected = oracle(tokens)
                    state, output, fake = run_game(tokens)
                    globals_ok = (public_module_state() == _module_globals_snapshot
                                  and not hasattr(simpleGame, 'score')
                                  and not hasattr(simpleGame, 'ans'))
                    record_path(tokens, state, output, globals_ok)

                    # Natural termination: always a finished state.
                    self.assertTrue(state['finished'])
                    self.assertEqual(state['index'], simpleGame.TOTAL_QUESTIONS)
                    # Score stays in bounds and matches the oracle.
                    self.assertGreaterEqual(state['score'], 0)
                    self.assertLessEqual(state['score'], simpleGame.TOTAL_QUESTIONS)
                    self.assertEqual(state['score'], expected['score'])
                    # Definite pass/fail endpoint.
                    self.assertIn(simpleGame.result_status(state),
                                  (simpleGame.STATUS_PASS, simpleGame.STATUS_FAIL))
                    self.assertEqual(simpleGame.result_status(state), expected['status'])
                    # Prompts and all printed text are byte-identical.
                    self.assertEqual(fake.prompts, expected['prompts'])
                    self.assertEqual(output, expected['output'])
                    # No unrelated global state was touched.
                    self.assertTrue(globals_ok)


class TestNaturalExit(unittest.TestCase):
    def test_eof_before_any_answer(self):
        state, output, _ = run_game('x')
        self.assertTrue(state['finished'])
        self.assertEqual(state['score'], 0)
        self.assertEqual(simpleGame.result_status(state), simpleGame.STATUS_FAIL)
        self.assertIn('Better luck next time', output)

    def test_eof_mid_game_settles_remaining_questions(self):
        state, output, _ = run_game('CCx')
        self.assertTrue(state['finished'])
        self.assertEqual(state['score'], 2)
        self.assertEqual(simpleGame.result_status(state), simpleGame.STATUS_PASS)
        self.assertIn('Nice! You passed!', output)

    def test_keyboard_interrupt_propagates(self):
        def raising_input(prompt=''):
            raise KeyboardInterrupt
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                simpleGame.play(input_func=raising_input)

    def test_non_string_answer_is_handled(self):
        fake = FakeInput([17, 'x'])  # int 17 normalizes to '17'
        with contextlib.redirect_stdout(io.StringIO()):
            state = simpleGame.play(input_func=fake)
        self.assertTrue(state['finished'])
        self.assertEqual(state['score'], 0)  # Q1 wrong, Q2 never asked (EOF)

    def test_main_entry_point(self):
        answers = iter(['tech with tim', '17', 'soccer', 'pizza'])
        with mock.patch('builtins.input', lambda prompt='': next(answers)):
            with contextlib.redirect_stdout(io.StringIO()) as buffer:
                state = simpleGame.main()
        self.assertEqual(state['score'], 4)
        self.assertIn('Nice! You passed!', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
