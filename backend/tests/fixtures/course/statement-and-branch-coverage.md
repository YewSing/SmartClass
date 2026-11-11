# Statement and Branch Coverage

Statement coverage measures the share of executable statements that a test suite
exercises. A suite reaches one hundred percent statement coverage when every line of
code has been run at least once. Statement coverage is the weakest structural coverage
criterion, because it can pass while the suite misses many bugs in decisions.

Branch coverage is stronger. It requires every decision in the program, such as an if
or a switch, to take both the true and the false outcome at least once. For an if
statement with no else clause, branch coverage still demands one test that skips the
body and one test that enters it.

Branch coverage is often called decision coverage. It subsumes statement coverage:
reaching full branch coverage also gives full statement coverage, because every
statement lies on some branch. A test suite that achieves branch coverage but not
condition coverage may still miss bugs that depend on the combination of several
conditions inside a single decision.
