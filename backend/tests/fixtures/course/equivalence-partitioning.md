# Equivalence Partitioning

Equivalence partitioning, or EP, divides the input domain of a program into
equivalence classes: groups of values the program is expected to treat identically.
Testing one representative value from each class is assumed to reveal the same faults
as testing every member of the class, so EP greatly reduces the number of test cases.

Partitions are drawn from both valid and invalid inputs. For an age field that accepts
0 to 120, the valid class is the range 0 to 120, and there are two invalid classes:
negative values and values above 120. A complete test set samples at least one value
from each class.

When a program takes several inputs, EP considers each input's classes independently
and then combines representative values, usually with an all-combinations or pairwise
strategy. The resulting test suite is much smaller than exhaustive testing but still
covers every behaviourally distinct category of input.
