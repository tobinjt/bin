"""Tests for colx."""

# import pytest
import colx

def test_argument_parsing():
  """Tests for argument parsing."""
  options = colx.parse_arguments(['1', 'asdf'])
  assert options.columns == [1]
  assert options.filenames == ['asdf']
