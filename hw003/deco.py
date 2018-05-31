from functools import update_wrapper


def disable(func):
    """
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:

    >>> memo = disable

    """
    return func


def decorator():
    """
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    """
    return


def countcalls(func):
    """
    Decorator that counts calls made to the function decorated.
    """

    def wrapper(*args):
        wrapper.calls += 1
        return func(*args)

    wrapper.calls = 0
    return wrapper


# Декоратор countcalls можно реализовать через класс
# class countcalls(object):
#     def __init__(self, func):
#         self.func = func
#         self.calls = 0
#
#     def __call__(self, *args):
#         self.calls += 1
#         return self.func(*args)


def memo(func):
    """
    Memoize a function so that it caches all return values for
    faster future lookups.
    """
    cache = {}

    def wrapper(*args):
        if args in cache:
            # print("from cache")
            return cache[args]
        else:
            cache[args] = result = func(*args)
            return result

    return wrapper

# Раскоментировав строчку ниже задизейблим memo
# memo = disable

# Декоратор memo можно реализовать через класс
# class memo(object):
#     def __init__(self, func):
#         self.func = func
#         self.cache = {}
#
#     def __call__(self, *args):
#         if args in args:
#             return self.cache[args]
#         else:
#             self.cache[args] = res = self.func(*args)
#             return res


def n_ary(func):
    """
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    """

    def wrapper(x, *args):
        return x if not args else func(x, wrapper(*args))

    return wrapper


def trace(intend):
    """
    Trace calls made to function decorated.

    @trace("____")
    def fib(n):
        ....

    >>> fib(3)
     --> fib(3)
    ____ --> fib(2)
    ________ --> fib(1)
    ________ <-- fib(1) == 1
    ________ --> fib(0)
    ________ <-- fib(0) == 1
    ____ <-- fib(2) == 2
    ____ --> fib(1)
    ____ <-- fib(1) == 1
     <-- fib(3) == 3

    """
    def wrapper(func):
        def internal(*args):
            print("{0} --> {1}({2})".format(wrapper.intend_level * intend, func.__name__, ", ".join(map(repr, args))))
            wrapper.intend_level += 1

            res = func(*args)
            print("{0} <-- {1}({2}) == {3}".format(
                (wrapper.intend_level - 1) * intend,
                func.__name__,
                ", ".join(map(repr, args)),
                res))

            wrapper.intend_level -= 1
            return res
        return internal

    wrapper.intend_level = 0
    return wrapper


# В исходном файле deco.py декораторы countcalls и memo изменены местами. Нужно их переставить,
# т.к. в противном случае при отработке memo теряется аттрибут функции calls,
# который инициализируется в countcalls
@countcalls
@memo
@n_ary
def foo(a, b):
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b):
    return a * b


# Поменял местами трассирующий и memo декораторы. В противном случае в трассирующем декораторе на print`е всплывает
# неверное имя исходной функции (всплывает имя декорирующей функции)
@countcalls
@memo
@trace(intend="####")
def fib(n):
    """Some doc"""
    return 1 if n <= 1 else fib(n-1) + fib(n-2)


def main():
    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    # print fib.__doc__
    fib(3)
    print(fib.calls, 'calls made')


if __name__ == '__main__':
    main()