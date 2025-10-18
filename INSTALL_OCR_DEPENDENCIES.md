# 📦 Installing OCR Dependencies for Study Sharper

This guide covers installing the system dependencies required for OCR (Optical Character Recognition) functionality in Study Sharper.

---

## 🪟 Windows Installation

### 1. Install Tesseract OCR

**Download:**
- Go to: https://github.com/UB-Mannheim/tesseract/wiki
- Download the latest installer (e.g., `tesseract-ocr-w64-setup-5.3.3.20231005.exe`)

**Install:**
1. Run the installer
2. **Important:** Check "Add to PATH" during installation
3. Default install location: `C:\Program Files\Tesseract-OCR`
4. Complete the installation

**Verify Installation:**
```powershell
tesseract --version
```
Should output: `tesseract 5.x.x`

**If PATH not set automatically:**
1. Open System Properties → Environment Variables
2. Edit "Path" in System Variables
3. Add: `C:\Program Files\Tesseract-OCR`
4. Restart terminal/IDE

### 2. Install Poppler

**Download:**
- Go to: https://github.com/oschwartz10612/poppler-windows/releases
- Download latest release (e.g., `Release-24.02.0-0.zip`)

**Install:**
1. Extract ZIP to a permanent location (e.g., `C:\Program Files\poppler`)
2. Add `C:\Program Files\poppler\Library\bin` to PATH
3. Restart terminal/IDE

**Verify Installation:**
```powershell
pdftoppm -v
```
Should output version information

### 3. Install Python Packages

```powershell
cd Study_Sharper_Backend
pip install -r requirements.txt
```

**Verify Python Packages:**
```powershell
python -c "import pytesseract, pdf2image; print('✅ All imports OK')"
```

---

## 🐧 Linux (Ubuntu/Debian) Installation

### 1. Install Tesseract OCR

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Verify:**
```bash
tesseract --version
```

### 2. Install Poppler

```bash
sudo apt-get install poppler-utils
```

**Verify:**
```bash
pdftoppm -v
```

### 3. Install Python Packages

```bash
cd Study_Sharper_Backend
pip install -r requirements.txt
```

**Verify:**
```bash
python3 -c "import pytesseract, pdf2image; print('✅ All imports OK')"
```

---

## 🍎 macOS Installation

### 1. Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Tesseract OCR

```bash
brew install tesseract
```

**Verify:**
```bash
tesseract --version
```

### 3. Install Poppler

```bash
brew install poppler
```

**Verify:**
```bash
pdftoppm -v
```

### 4. Install Python Packages

```bash
cd Study_Sharper_Backend
pip3 install -r requirements.txt
```

**Verify:**
```bash
python3 -c "import pytesseract, pdf2image; print('✅ All imports OK')"
```

---

## 🐳 Docker Installation (Optional)

If deploying with Docker, add to your Dockerfile:

```dockerfile
# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

---

## 🧪 Testing Installation

### Quick Test Script

Create a file `test_ocr.py`:

```python
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import io

def test_tesseract():
    """Test Tesseract OCR"""
    try:
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract version: {version}")
        return True
    except Exception as e:
        print(f"❌ Tesseract error: {e}")
        return False

def test_pdf2image():
    """Test pdf2image (Poppler)"""
    try:
        # This will fail if Poppler is not installed
        from pdf2image.exceptions import PDFInfoNotInstalledError
        print("✅ pdf2image imported successfully")
        return True
    except Exception as e:
        print(f"❌ pdf2image error: {e}")
        return False

def test_ocr_functionality():
    """Test actual OCR on a simple image"""
    try:
        # Create a simple test image with text
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (200, 50), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 10), "Test OCR", fill='black')
        
        # Perform OCR
        text = pytesseract.image_to_string(img)
        
        if "Test" in text or "OCR" in text:
            print(f"✅ OCR working! Extracted: {text.strip()}")
            return True
        else:
            print(f"⚠️ OCR extracted unexpected text: {text.strip()}")
            return False
    except Exception as e:
        print(f"❌ OCR functionality error: {e}")
        return False

if __name__ == "__main__":
    print("Testing OCR Dependencies...\n")
    
    results = {
        "Tesseract": test_tesseract(),
        "pdf2image": test_pdf2image(),
        "OCR Functionality": test_ocr_functionality()
    }
    
    print("\n" + "="*50)
    print("Test Results:")
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test}: {status}")
    
    if all(results.values()):
        print("\n🎉 All tests passed! OCR is ready to use.")
    else:
        print("\n⚠️ Some tests failed. Please check installation.")
```

Run the test:
```bash
python test_ocr.py
```

---

## 🔧 Troubleshooting

### Windows: "tesseract is not recognized"

**Solution:**
1. Verify Tesseract is installed: Check `C:\Program Files\Tesseract-OCR`
2. Add to PATH manually:
   - System Properties → Environment Variables
   - Edit "Path" → New → `C:\Program Files\Tesseract-OCR`
3. Restart terminal
4. Test: `tesseract --version`

**Alternative:** Set path in Python code:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Windows: "Unable to get page count. Is poppler installed?"

**Solution:**
1. Download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler`
3. Add `C:\Program Files\poppler\Library\bin` to PATH
4. Restart terminal
5. Test: `pdftoppm -v`

### Linux: "tesseract: command not found"

**Solution:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### macOS: "tesseract: command not found"

**Solution:**
```bash
brew install tesseract
```

### Python Import Error: "No module named 'pytesseract'"

**Solution:**
```bash
pip install pytesseract pdf2image
```

### OCR Returns Empty String

**Possible Causes:**
1. Image quality too low
2. Text too small
3. Wrong language (default is English)

**Solutions:**
- Increase image DPI
- Preprocess image (contrast, brightness)
- Specify language: `pytesseract.image_to_string(img, lang='eng')`

---

## 📊 System Requirements

### Minimum Requirements
- **Disk Space:** 500MB for Tesseract + Poppler
- **RAM:** 2GB available for OCR processing
- **CPU:** 2+ cores

### Recommended Requirements
- **Disk Space:** 1GB (includes language packs)
- **RAM:** 4GB+ for smooth processing
- **CPU:** 4+ cores for faster OCR

---

## 🌍 Additional Languages (Optional)

Tesseract supports 100+ languages. To add more:

### Windows
Download language data files from:
https://github.com/tesseract-ocr/tessdata

Place `.traineddata` files in:
`C:\Program Files\Tesseract-OCR\tessdata\`

### Linux/macOS
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr-[lang]

# macOS
brew install tesseract-lang
```

### Usage in Python
```python
# Spanish
text = pytesseract.image_to_string(img, lang='spa')

# Multiple languages
text = pytesseract.image_to_string(img, lang='eng+spa+fra')
```

---

## 🚀 Production Deployment

### Render.com / Railway / Heroku

Add to your buildpack or Dockerfile:

```bash
# Install system dependencies
apt-get update
apt-get install -y tesseract-ocr poppler-utils
```

### AWS EC2 / DigitalOcean

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

### Vercel / Netlify (Backend)

These platforms may not support system dependencies. Consider:
1. Using a separate backend service (Render, Railway)
2. Using cloud OCR API (Google Vision, AWS Textract)

---

## ✅ Installation Complete

Once all tests pass, you're ready to use OCR functionality in Study Sharper!

**Next Steps:**
1. Run database migration: `006_add_ocr_tracking.sql`
2. Start backend server
3. Upload a scanned PDF to test
4. Check for "Scanned" badge in UI

---

## 📚 Additional Resources

- **Tesseract Documentation:** https://tesseract-ocr.github.io/
- **Tesseract GitHub:** https://github.com/tesseract-ocr/tesseract
- **Poppler Documentation:** https://poppler.freedesktop.org/
- **pytesseract PyPI:** https://pypi.org/project/pytesseract/
- **pdf2image PyPI:** https://pypi.org/project/pdf2image/

---

**Need Help?** Check the troubleshooting section or create an issue in the repository.
