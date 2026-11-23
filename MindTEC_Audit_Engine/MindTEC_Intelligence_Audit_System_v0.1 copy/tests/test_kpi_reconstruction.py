"""Synthetic tests of reconstructed KPI matrix input validation."""
import importlib.util
import io
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "interface" / "pages" / "12_kpi_reconstruction.py"
spec = importlib.util.spec_from_file_location("mindtec_reconstruction", PAGE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CSV = (
    "mes,empresa,categoria,marca,indicador,publicado_texto,"
    "reconstruccion_anterior,recalculado_fuentes,verificacion_recalculado,"
    "escenario_no_oficial,clasificacion,evidencia_historica,pendiente_para_certificar\n"
    "2026-09,CBN,gaseosas,Demo,Distribución numérica,20%,0.2,0.2,"
    "Reproducción numérica coincide,,RECALCULO CON RESERVAS,20/100,Por acreditar\n"
)


class MatrixTests(unittest.TestCase):
    def test_valid_matrix(self):
        frame = module._read(io.StringIO(CSV))
        self.assertEqual(len(frame), 1)
        self.assertEqual(module._counts(frame), (1, 1, 1, 0))

    def test_duplicate_keys_blocked(self):
        with self.assertRaisesRegex(ValueError, "duplicadas"):
            module._read(io.StringIO(CSV + CSV.splitlines()[1] + "\n"))

    def test_required_columns(self):
        with self.assertRaisesRegex(ValueError, "requeridas"):
            module._read(io.StringIO("mes,marca\n2026-09,Demo\n"))


if __name__ == "__main__":
    unittest.main()
