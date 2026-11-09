# Sentetik oyun 2 — tek menüde çatallı dal: if has_water: heal else: damage
default has_water = False
default hp = 100

label start:
    "Kuru vadide kalabilirsin."
    menu:
        "Kutu beklemesi gir":
            if has_water:
                $ hp += 10
                "Icine su doldur."
                jump safe_end
            else:
                $ hp -= 40
                "Su yok, hasar aldi."
                jump danger_end

label safe_end:
    "Safely out."
    return

label danger_end:
    "HP critical."
    $ renpy.quit()
