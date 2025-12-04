from PIL import Image, ImageDraw

# Crear ícono simple
img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Dibujar mano
draw.ellipse([20, 20, 44, 44], fill=(79, 204, 163), outline=(15, 52, 96))

# Guardar
os.makedirs("assets", exist_ok=True)
img.save("assets/icon.png")
img.save("assets/icon.ico", format="ICO")