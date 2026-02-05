@echo off
title SIVI AFD Validator v2.0

echo ============================================================
echo   SIVI AFD XML Validator v2.0 - Gap Analysis Implementation
echo ============================================================
echo.
echo   Engines:
echo     0. XSD Validatie (structuur, hierarchie)
echo     1. Schema Validatie (labels, codes, decimale precisie)
echo     2. Business Rules (premies, datums, BSN, IBAN, branche)
echo     3. LLM Semantische Analyse (AI-powered)
echo     4. XPath Verbandscontroles (relatie controles)
echo     5. Encoding ^& Data Quality (UTF-8, BOM, placeholders)
echo     F. Certificering (verzendklaar garantie)
echo.
echo ============================================================
echo.

cd /d "%~dp0"

echo Dependencies installeren...
python -m pip install -r requirements.txt -q
echo.

echo Browser wordt geopend op http://localhost:8000 ...
echo.

:: Open browser after a short delay (gives server time to start)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

echo Server starten...
echo (Sluit dit venster om de server te stoppen)
echo.
echo CLI gebruik:
echo   python sivi_validator.py input.xml
echo   python sivi_validator.py input.xml --engines 0,1,2,4,5 -o xlsx
echo   python sivi_validator.py input.xml --all-engines  (incl. LLM)
echo   python sivi_validator.py input.xml --show-version
echo   python sivi_validator.py input.xml --sivi-cert-info
echo.

python -m uvicorn api.main:app --port 8000

pause
