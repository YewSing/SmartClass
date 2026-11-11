# Boundary Value Analysis

Boundary value analysis, usually shortened to BVA, is a black-box testing technique
that designs test cases around the edges of the input domain. The idea is that
programmers most often make mistakes at the boundaries of a range, such as the
minimum, the maximum, and the values immediately inside and outside them.

For a field that accepts integers from 1 to 100 inclusive, BVA suggests testing the
values 0, 1, 2, 99, 100 and 101. The classic three-point rule tests the minimum, the
minimum minus one and the minimum plus one, plus the maximum, the maximum minus one
and the maximum plus one, which yields six test cases.

BVA pairs naturally with equivalence partitioning. Equivalence partitioning first
divides the input domain into classes of values that should behave the same, and then
boundary value analysis picks the values at the edges of each class, where off-by-one
errors are most likely to hide.
