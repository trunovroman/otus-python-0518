import unittest
import inspect
import log_analyzer as la


class TestConfigAttrTypes(unittest.TestCase):

    def test_undefined_values(self):
        # Класс Configuration должен генерить исключение, если не определен аттрибут, соответствующий свойству
        properties = inspect.getmembers(la.Configuration, lambda o: isinstance(o, property))
        obj = la.Configuration()
        obj.load_from_object({})
        for prop in properties:
            with self.assertRaises(KeyError):
                getattr(obj, prop[0])

    def test_log_level(self):
        # Аттрибут LOG_LEVEL не может принимать никакое другое значение, кроме INFO, ERROR or CRITICAL
        cfg = la.Configuration()
        cfg.load_from_object({"LOG_LEVEL": "DEBUG"})
        with self.assertRaises(ValueError):
            cfg.log_level()

        # Аттрибут LOG_LEVEL должен быть строкой
        cfg = la.Configuration()
        cfg.load_from_object({"LOG_LEVEL": 1})
        with self.assertRaises(TypeError):
            cfg.log_level()

    def test_error_percent(self):
        # Процент количества ошибок должен быть >= 0 и <= 100
        cfg = la.Configuration()
        cfg.load_from_object({"ERROR_PERCENT": -1})
        with self.assertRaises(ValueError):
            cfg.error_percent()

        cfg = la.Configuration()
        cfg.load_from_object({"ERROR_PERCENT": 101})
        with self.assertRaises(ValueError):
            cfg.error_percent()

        cfg = la.Configuration()
        cfg.load_from_object({"ERROR_PERCENT": 100})
        self.assertEqual(cfg.error_percent, 100)

        cfg = la.Configuration()
        cfg.load_from_object({"ERROR_PERCENT": 0})
        self.assertEqual(cfg.error_percent, 0)

    def test_round_places(self):
        # Количество знаков после запятой для округления дробных значений должно быть > 0
        cfg = la.Configuration()
        cfg.load_from_object({"ROUND_PLACES": -1})
        with self.assertRaises(ValueError):
            cfg.round_places()

        cfg = la.Configuration()
        cfg.load_from_object({"ROUND_PLACES": 3})
        self.assertEqual(cfg.round_places, 3)

if __name__ == '__main__':
    unittest.main()
