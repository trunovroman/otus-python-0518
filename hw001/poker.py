# -----------------
# Реализуйте функцию best_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. У каждой карты есть масть(suit) и
# ранг(rank)
# Масти: трефы(clubs, C), пики(spades, S), червы(hearts, H), бубны(diamonds, D)
# Ранги: 2, 3, 4, 5, 6, 7, 8, 9, 10 (ten, T), валет (jack, J), дама (queen, Q), король (king, K), туз (ace, A)
# Например: AS - туз пик (ace of spades), TH - дестяка черв (ten of hearts), 3C - тройка треф (three of clubs)

# Задание со *
# Реализуйте функцию best_wild_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. Кроме прочего в данном варианте "рука"
# может включать джокера. Джокеры могут заменить карту любой
# масти и ранга того же цвета, в колоде два джокерва.
# Черный джокер '?B' может быть использован в качестве треф
# или пик любого ранга, красный джокер '?R' - в качестве черв и бубен
# любого ранга.

# Одна функция уже реализована, сигнатуры и описания других даны.
# Вам наверняка пригодится itertools
# Можно свободно определять свои функции и т.п.
# -----------------

import itertools
import copy

BLACK_JOKER = '?B'
RED_JOKER = '?R'
BLACK_JOKER_PLACEHOLDERS = ['1C', '2C', '3C', '4C', '5C', '6C', '7C', '8C', '9C', 'TC', 'JC', 'QC', 'KC', 'AC',
                            '1S', '2S', '3S', '4S', '5S', '6S', '7S', '8S', '9S', 'TS', 'JS', 'QS', 'KS', 'AS']
RED_JOKER_PLACEHOLDERS = ['1H', '2H', '3H', '4H', '5H', '6H', '7H', '8H', '9H', 'TH', 'JH', 'QH', 'KH', 'AH',
                          '1D', '2D', '3D', '4D', '5D', '6D', '7D', '8D', '9D', 'TD', 'JD', 'QD', 'KD', 'AD']


# ----------------
# Custom functions
# ----------------

def replace_in_list(item_list, old_item, new_item):
    """Копирует список item_list (т.е. не меняет исходный) и заменяет в нем элемент old_item на new_item"""
    a = copy.deepcopy(item_list)
    a[a.index(old_item)] = new_item
    return a


def replace_cards(hand_list, old_card, new_card_list):
    """Получает на вход список рук, ищет в каждой руке old_card и, если находит, то по очереди подставляет
    вместо нее элементы из new_card_list. На выходе имеем список из len(new_card_list) рук"""
    result = []
    for hand in hand_list:
        if old_card in hand:
            # Do set(new_card_list) - set(hand) to exclude duplicate cards from result hand
            result.extend([replace_in_list(hand, old_card, new_card) for new_card in set(new_card_list) - set(hand)])
        else:
            result.append(hand)

    return result


def internal_best_hand(hand_list):
    """Универсальная функция, которая используется для поиска лучших рук. Используется в best_hand и в best_wild_hand

    Описание алгоритма:
    1. В общем случае на вход подается несколько рук по 7 карт (для случая с джокерами)
    2. Для всех этих рук формируются сочетания из 5 по 7 и все складываются в один список
    3. Этот список очищается от дублей (при помощи itertools.groupby) и для каждой руки из 5 карт считается ранг
    4. Выбираем руку из 5 карт с наибольшим рангом"""
    # Формируем все комбинации по 5 карт для всех возможных рук из 7 карт.
    all_combinations = []
    for x in hand_list:
        combination = [sorted(list(y), reverse=True) for y in itertools.combinations(x, 5)]
        all_combinations.extend(combination)

    # Combine hand and rank for all items in all_combinations list. Exclude duplicates by iterbools.groupby operation
    combinations_with_rank = list(
        (hand_rank(key), key)
        for key, group in itertools.groupby(sorted(all_combinations))
    )

    combinations_with_rank.sort(reverse=True)
    return combinations_with_rank[0][1]


def get_rank(rank_symbol):
    """Возвращает числовой эквивалент ранга карты"""
    if rank_symbol.isdigit():
        return int(rank_symbol)
    elif rank_symbol == "T":    # десятка
        return 10
    elif rank_symbol == "J":    # валет
        return 11
    elif rank_symbol == "Q":    # дама
        return 12
    elif rank_symbol == "K":    # король
        return 13
    elif rank_symbol == "A":    # туз
        return 14
    else:
        return 0


# -----------------
# Initial functions
# -----------------

def hand_rank(hand):
    """Возвращает значение определяющее ранг 'руки'"""
    ranks = card_ranks(hand)
    if straight(ranks) and flush(hand):
        return (8, max(ranks))
    elif kind(4, ranks):
        return (7, kind(4, ranks), kind(1, ranks))
    elif kind(3, ranks) and kind(2, ranks):
        return (6, kind(3, ranks), kind(2, ranks))
    elif flush(hand):
        return (5, ranks)
    elif straight(ranks):
        return (4, max(ranks))
    elif kind(3, ranks):
        return (3, kind(3, ranks), ranks)
    elif two_pair(ranks):
        return (2, two_pair(ranks), ranks)
    elif kind(2, ranks):
        return (1, kind(2, ranks), ranks)
    else:
        return (0, ranks)


def card_ranks(hand):
    """Возвращает список рангов (его числовой эквивалент),
    отсортированный от большего к меньшему"""
    return sorted(list(get_rank(x[0]) for x in hand), reverse=True)


def flush(hand):
    """Возвращает True, если все карты одной масти.

    Описание алгоритма:
    1. Группируем по масти. Если получилась одна группа, значит масть у всех карт одинаковая
    """
    return len(list(itertools.groupby(hand, lambda x: x[1]))) == 1  # группируем по масти


def straight(ranks):
    """Возвращает True, если отсортированные ранги формируют последовательность 5ти,
    где у 5ти карт ранги идут по порядку (стрит)

    Описание алгоритма:
    1. По порядку идущие ранги — это арифметическая прогрессия. Получаем ее, начиная с первого элемента
    и сравниваем со списком ranks
    """
    arithmetic_progression = list(range(ranks[0], ranks[0] - len(ranks), -1))
    return arithmetic_progression == ranks


def kind(n, ranks):
    """Возвращает первый ранг, который n раз встречается в данной руке.
    Возвращает None, если ничего не найдено"""
    for x in ranks:
        if ranks.count(x) == n:
            return x

    return None


def two_pair(ranks):
    """Если есть две пары, то возврщает два соответствующих ранга,
    иначе возвращает None

    Описание алгоритма:
    1. Собираем элементы в группы
    2. Отбираем те группы, в которых 2 и более элементов
    3. Если таких групп 2, то True, иначе None
    """
    groups = itertools.groupby(ranks)
    pairs = [y[0] for y in itertools.takewhile(lambda x: len(list(x[1])) >= 2, groups)]
    return pairs if len(pairs) == 2 else None


def best_hand(hand):
    """Из "руки" в 7 карт возвращает лучшую "руку" в 5 карт"""
    return internal_best_hand([hand])


def best_wild_hand(hand):
    """best_hand но с джокерами

    Описание алгоритма:
    1. Формируем все возможные руки по 7, заменяя джокеры на конкретные карты
    2. А дальше, почти как в best_hand...
    """

    # Start to create all possible hand combinations with 7 cards include jokers
    hand_list = [hand]

    # Replacing black and than red jokers
    hand_list = replace_cards(hand_list, BLACK_JOKER, BLACK_JOKER_PLACEHOLDERS)
    hand_list = replace_cards(hand_list, RED_JOKER, RED_JOKER_PLACEHOLDERS)

    return internal_best_hand(hand_list)


def test_best_hand():
    print("test_best_hand...")
    assert (sorted(best_hand("6C 7C 8C 9C TC 5C JS".split()))
            == ['6C', '7C', '8C', '9C', 'TC'])
    assert (sorted(best_hand("TD TC TH 7C 7D 8C 8S".split()))
            == ['8C', '8S', 'TC', 'TD', 'TH'])
    assert (sorted(best_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print('OK')


def test_best_wild_hand():
    print("test_best_wild_hand...")
    assert (sorted(best_wild_hand("6C 7C 8C 9C TC 5C ?B".split()))
            == ['7C', '8C', '9C', 'JC', 'TC'])
    assert (sorted(best_wild_hand("TD TC 5H 5C 7C ?R ?B".split()))
            == ['7C', 'TC', 'TD', 'TH', 'TS'])
    assert (sorted(best_wild_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print('OK')


if __name__ == '__main__':
    test_best_hand()
    test_best_wild_hand()
