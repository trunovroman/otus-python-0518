import unittest
import log_analyzer as la


class TestURLStatistic(unittest.TestCase):
    def test_calculation(self):
        data = {
            "http://url.com/1": [1.1, 1.2, 0.5, 0.001],
            "http://url.com/2": [2.4, 1.1],
            "http://url.com/3": [1.1, 1.3, 1.3],
            "http://url.com/4": [1.1, 1.3],
        }
        round_places = 3
        report_size = 2

        # Получаем список из N элементов
        items = la.calculate_statistic(data, round_places, report_size)
        item_top = items[0]

        # Проверяем метод, возвращающий первые N элементов, отсортированных по убыванию time_sum
        self.assertEqual(len(items), report_size)  # длина этого списка должна быть равна N
        self.assertEqual(item_top["url"], "http://url.com/3")  # третий URL — это URL с наибольшим time_sum

        # Проверяем расчет аналитических показателей для отдельно выбранного URL`а
        # Руками рассчитываем все показатели и вписываем для сравнения
        self.assertEqual(item_top["count"], 3)
        self.assertAlmostEqual(item_top["count_percent"], 27.273, round_places)
        self.assertAlmostEqual(item_top["time_sum"], 3.7, round_places)
        self.assertAlmostEqual(item_top["time_percent"], 29.836, round_places)
        self.assertAlmostEqual(item_top["time_avg"], 1.233, round_places)
        self.assertEqual(item_top["time_max"], 1.3)
        self.assertEqual(item_top["time_median"], 1.3)  # медиана для нечетного количества элементов

        # Для подсчета медианы с четным количеством элементов, выбираем подходящий URL
        item_last = items[-1]  # Это будет второй URL
        self.assertAlmostEqual(item_last["time_median"], 1.75, round_places)  # медиана для четного количества элементов


if __name__ == '__main__':
    unittest.main()
