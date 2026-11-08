from django.db import migrations


PRODUCTS = [
    ("midnight-garden-drops", "Midnight Garden Drops", "Statement earrings",
     "Deep blue stones and bright detailing bring a bold, dressed-up finish to evening looks and special occasions.",
     "assets/img/portfolio/1.jpg", "2450.00"),
    ("golden-hour-hoops", "Golden Hour Hoops", "Earrings",
     "Easy-to-style gold-tone hoops and sculptural shapes make a warm, versatile accent for weekdays and weekends.",
     "assets/img/portfolio/2.jpg", "1850.00"),
    ("soft-glow-pearl-drops", "Soft Glow Pearl Drops", "Pearl details",
     "A softly shining pearl and a sculptural top give this pair a graceful look for daytime gatherings or dinner.",
     "assets/img/portfolio/3.jpg", "2100.00"),
    ("everyday-link-bracelet", "Everyday Link Bracelet", "Bracelets",
     "A classic linked silhouette adds shine on its own and pairs naturally with a watch or other wrist favourites.",
     "assets/img/portfolio/4.jpg", "1500.00"),
    ("colour-story-cuffs", "Colour Story Cuffs", "Colourful accents",
     "Textured bands in expressive colours bring an easy pop to simple outfits. Wear one or stack a few for extra impact.",
     "assets/img/portfolio/5.jpg", "1200.00"),
    ("bloom-pendant-necklace", "Bloom Pendant Necklace", "Necklaces",
     "A delicate chain and flower-inspired pendant create a graceful focal point for an open neckline or layered look.",
     "assets/img/portfolio/6.jpg", "1950.00"),
    ("golden-knot-bangle", "Golden Knot Bangle", "Bracelets",
     "A clean, sculptural shape with a knot detail makes this bangle an understated accent that still catches the eye.",
     "assets/img/portfolio/7.jpg", "1350.00"),
    ("ginkgo-leaf-pendant", "Ginkgo Leaf Pendant", "Necklaces",
     "Inspired by the graceful shape of a leaf, this pendant adds a distinctive, nature-led detail to an everyday outfit.",
     "assets/img/portfolio/8.jpg", "2200.00"),
    ("the-layered-edit", "The Layered Edit", "Layering inspiration",
     "A mix of fine chains and delicate accents shows how simple pieces combine for a look that feels entirely your own.",
     "assets/img/portfolio/9.jpg", "2600.00"),
    ("silver-sculpture-rings", "Silver Sculpture Rings", "Rings",
     "Polished, sculptural silver-tone shapes make a striking little detail to wear alone or mix with your favourites.",
     "assets/img/portfolio/10.jpg", "1450.00"),
    ("rose-light-stackers", "Rose Light Stackers", "Rings",
     "A delicate ring set with a soft, romantic finish—an easy gift idea or a sweet addition to your own jewellery box.",
     "assets/img/portfolio/11.jpg", "1750.00"),
    ("time-and-shine", "Time & Shine", "Watches and bracelets",
     "A watch-and-bracelet pairing brings function and a little sparkle together for a polished wrist stack.",
     "assets/img/portfolio/12.jpg", "3200.00"),
    ("golden-heirloom-pendant", "Golden Heirloom Pendant", "Statement necklaces",
     "An ornate gold-tone pendant with intricate detail makes a confident centrepiece for celebrations and special evenings.",
     "assets/img/portfolio/13.jpg", "2850.00"),
    ("colour-pop-statement-set", "Colour Pop Statement Set", "Statement accessories",
     "Vibrant stones and playful details add personality to a dressed-up look. Choose one feature or make it a set.",
     "assets/img/portfolio/14.jpg", "2300.00"),
    ("the-keepsake-box", "The Keepsake Box", "Gift sets",
     "A curated selection inspired by the Meine display: a thoughtful place to start when choosing a jewellery gift.",
     "assets/img/portfolio/15.jpg", "1800.00"),
]


def seed_catalog(apps, schema_editor):
    Product = apps.get_model("myapp", "Product")
    Product.objects.using(schema_editor.connection.alias).bulk_create([
        Product(
            slug=slug,
            name=name,
            category=category,
            description=description,
            image=image,
            price_kes=price,
            sort_order=index,
        )
        for index, (slug, name, category, description, image, price) in enumerate(PRODUCTS, start=1)
    ])


def remove_catalog(apps, schema_editor):
    Product = apps.get_model("myapp", "Product")
    Product.objects.using(schema_editor.connection.alias).filter(
        slug__in=[product[0] for product in PRODUCTS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, remove_catalog),
    ]
