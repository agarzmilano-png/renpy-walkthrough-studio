# Inspirasyon: sentetik oyun 1 — klasik A(+1)/B(-1) romance menüsü + analiz pedagogu gibi sonuclar
define l = Character('Luna')
default love = 0
default trust = 0

label start:
    "The story starts here."
    menu:
        "Luna'ya yaklaş ve destek ver (+1 love)":
            $ love += 1
            jump good_branch
        "Uzak dur ve ayrıl (-1 love)":
            $ love -= 1
            jump bad_branch

label good_branch:
    l "Teşekkür ederim!"
    jump ending_good

label bad_branch:
    l "Bana karşı soğuktun..."
    jump ending_bad

label ending_good:
    "İyi son."
    return

label ending_bad:
    "Kötü son."
    $ renpy.quit()
