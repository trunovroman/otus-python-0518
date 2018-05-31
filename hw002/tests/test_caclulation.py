import unittest
import log_analyzer as la


class TestURLStatistic(unittest.TestCase):
    def test_single_url_calc(self):
        round_places = 3
        stat = la.URLStatistic(round_places)
        for i in range(1, 101):
            stat.add_url("http://url.com/1", i)

        self.assertEqual(stat.total_count, 100)
        self.assertEqual(stat.total_time_sum, 5050)

    def test_multiply_url_calc(self):
        round_places = 3
        stat = la.URLStatistic(round_places)  # точность округления 3 знака

        # Первый URL — time_sum = 2.801
        stat.add_url("http://url.com/1", 1.1)
        stat.add_url("http://url.com/1", 1.2)
        stat.add_url("http://url.com/1", 0.5)
        stat.add_url("http://url.com/1", 0.001)

        # Второй URL — time_sum = 3.49997
        stat.add_url("http://url.com/2", 2.4)
        stat.add_url("http://url.com/2", 1.1)

        # Третий URL — time_sum = 3.49998
        stat.add_url("http://url.com/3", 1.1)
        stat.add_url("http://url.com/3", 1.3)
        stat.add_url("http://url.com/3", 1.3)

        # Четвертый URL — time_sum = 2.4
        stat.add_url("http://url.com/4", 1.1)
        stat.add_url("http://url.com/4", 1.3)

        # Получаем список из N элементов
        items = stat.get_items(2)
        item_top = items[0]

        # Проверяем метод, возвращающий первые N элементов, отсортированных по убыванию time_sum
        self.assertEqual(len(items), 2)  # длина этого списка должна быть равна N
        self.assertEqual(item_top.url, "http://url.com/3")  # третий URL — это URL с наибольшим time_sum

        # Проверяем расчет аналитических показателей для отдельно выбранного URL`а
        # Руками рассчитываем все показатели и вписываем для сравнения
        self.assertEqual(item_top.count, 3)
        self.assertAlmostEqual(item_top.count_percent, 27.273, round_places)
        self.assertAlmostEqual(item_top.time_sum, 3.7, round_places)
        self.assertAlmostEqual(item_top.time_percent, 29.836, round_places)
        self.assertAlmostEqual(item_top.time_avg, 1.233, round_places)
        self.assertEqual(item_top.time_max, 1.3)
        self.assertEqual(item_top.time_median, 1.3)  # медиана для нечетного количества элементов

        # Для подсчета медианы с четным количеством элементов, выбираем подходящий URL
        item_last = items[-1]  # Это будет второй URL
        self.assertAlmostEqual(item_last.time_median, 1.75, round_places)  # медиана для четного количества элементов


if __name__ == '__main__':
    unittest.main()
