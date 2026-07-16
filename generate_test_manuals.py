import fitz  # PyMuPDF


def create_pdf(filename: str, content: list):
    doc = fitz.open()
    page = doc.new_page()
    
    y = 50
    # Add manual title header
    page.insert_text((50, y), "CardioTrack CT-200 Blood Pressure Monitor", fontsize=16, fontname="hebo")
    y += 40
    
    for item in content:
        text = item["text"]
        size = item.get("size", 10)
        font = "hebo" if item.get("bold") else "helv"
        
        # Simple line wrapping: split by newline or write directly
        lines = text.split("\n")
        for line in lines:
            page.insert_text((50, y), line, fontsize=size, fontname=font)
            y += size + 5
        y += 10
        
    doc.save(filename)
    doc.close()
    print(f"Successfully generated PDF: {filename}")


# -------------------------------------------------------------
# VERSION 1 CONTENT
# -------------------------------------------------------------
v1_content = [
    {"text": "1. Introduction", "size": 14, "bold": True},
    {"text": "The CardioTrack CT-200 is a digital monitor intended for use in measuring\nblood pressure and pulse rate in adult patient populations.", "size": 10},
    
    {"text": "2. Safety Precautions", "size": 14, "bold": True},
    {"text": "WARNING: Do not use this monitor on infants or individuals who cannot\nexpress consent.", "size": 10},
    {"text": "WARNING: Avoid operating the device near strong electromagnetic fields,\nsuch as microwave ovens or cellular phones.", "size": 10},
    
    {"text": "3. Measurement Guidelines", "size": 14, "bold": True},
    {"text": "3.1 Cuff Inflation", "size": 12, "bold": True},
    {"text": "Wrap the cuff snugly around your upper left arm, about 1-2 cm above the elbow joint.\nPress the Start button. The pump will automatically inflate the cuff to 150 mmHg.", "size": 10}
]

# -------------------------------------------------------------
# VERSION 2 CONTENT (Modified warnings, cuff limits, and a new section)
# -------------------------------------------------------------
v2_content = [
    {"text": "1. Introduction", "size": 14, "bold": True},
    {"text": "The CardioTrack CT-200 is a digital monitor intended for use in measuring\nblood pressure and pulse rate in adult patient populations.", "size": 10},
    
    {"text": "2. Safety Precautions", "size": 14, "bold": True},
    # Modified (added "toddlers")
    {"text": "WARNING: Do not use this monitor on infants, toddlers, or individuals\nwho cannot express consent.", "size": 10},
    {"text": "WARNING: Avoid operating the device near strong electromagnetic fields,\nsuch as microwave ovens or cellular phones.", "size": 10},
    
    {"text": "3. Measurement Guidelines", "size": 14, "bold": True},
    {"text": "3.1 Cuff Inflation", "size": 12, "bold": True},
    # Modified (limit raised to 180 mmHg)
    {"text": "Wrap the cuff snugly around your upper left arm, about 1-2 cm above the elbow joint.\nPress the Start button. The pump will automatically inflate the cuff to 180 mmHg.", "size": 10},
    
    # New section added
    {"text": "3.2 Device Calibration", "size": 12, "bold": True},
    {"text": "The monitor performs automatic self-calibration during each power-on cycle.\nAnnual calibration verification by an authorized service center is recommended.", "size": 10}
]

if __name__ == "__main__":
    create_pdf("CardioTrack_v1.pdf", v1_content)
    create_pdf("CardioTrack_v2.pdf", v2_content)
