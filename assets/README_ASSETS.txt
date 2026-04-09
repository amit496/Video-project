Folder layout (client / daily workflow)

1) anchor/
   - Yahan kam se kam ek news anchor ki image rakho: .jpg / .png / .webp
   - Abhi agar folder khali hai to video placeholder background use karega.
   - B-roll mode mein anchor chhota corner mein dikhega (picture-in-picture).

2) news_today/
   - Har din run se pehle yahan aaj ki news se related images ya chhote video clips daalo.
   - Best practice: story-wise prefix lagao:
       01_*.jpg / 01_*.mp4  -> Story 1 visuals
       02_*.png             -> Story 2 visuals
       ...
     (prefix na ho to files general pool mein jayengi)
   - Jo files zyada hongi, voice ki lambai unke beech barabar baant di jayegi.
   - Sirf licensed / copyright-safe media use karo (Pexels, Pixabay, apni shoot, wagaira).

Optional: .env mein NEWS_MEDIA_DIR se kisi aur folder ka path de sakte ho (jaise dated folder).

Agar roz folder khali chhodna ho: .env mein PEXELS_API_KEY lagao — pipeline khali folder par Pexels se headline ke hisaab se images le lega (license Pexels terms ke mutabiq).
