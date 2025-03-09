# Font Width Converter
Converts any given Minecraft font into a new font that replaces each character with a space character that is as wide as the original character but multiplied by a given factor.

The included fonts have been generated using the script's default settings, meaning that only the ascii characters are included from the default unihex characters.

# How to use the font
Replacing a text with the same width in space characters does not immediately seem useful, but there is a number of cases where such a font can be helpful.

For example, imagine you want to display a 5 digit text box, and inside there, show a scoreboard number.
The naive approach would be this:
```hs
scoreboard objectives add gold dummy
scoreboard players set team_blue gold 1234
scoreboard players set team_red gold 50
item replace entity @s weapon.mainhand with minecraft:written_book[minecraft:written_book_content={author:"",title:"",pages:[ \
    ["[",{score:{name:team_blue,objective:gold}},"]", "\n", \
     "[",{score:{name:team_red, objective:gold}},"]"]  \
]}]
```
However, after running these commands, you'll see that the alignment between the fields doesn't match, because each one will just be as wide as the number inside, instead of each text field having a fixed width.

To fix that, add a negative version of the number to each display, and it will cancel out its width:
```hs
item replace entity @s weapon.mainhand with minecraft:written_book[minecraft:written_book_content={author:"",title:"",pages:[ \
    ["[        ",{score:{name:team_blue,objective:gold},font:default_neg},{score:{name:team_blue,objective:gold}},"]", "\n", \
     "[        ",{score:{name:team_red, objective:gold},font:default_neg},{score:{name:team_red,objective:gold}},"]"]  \
]}]
```
Note that because the numbers now have a total of 0 width, you still need to add extra space to set the width of the text box they're displayed in. In the example I used literal space signs, but you can of course use actual space characters as well.

## Aligning text
You can also see that adding the negative space *before* the text caused it to be right-aligned, which is what you would want for numbers. Displaying the negative space *after* the text would instead cause it to stay left-aligned.

The same also happens in slots that would originally center their text. For example, this ends up being left-aligned:
```hs
/title @s actionbar ["",{text:"Hello World"},{text:"Hello World",font:default_neg}]
```
For cases like this where you want something to be centered, you can first display half the negative space, then display the text, and only then display the second half of the negative space:
```hs
/title @s actionbar ["",{text:"Hello World",font:default_neg_half},{text:"Hello World"},{text:"Hello World",font:default_neg_half}]
```

# How to use the script
First, install the required packages:
```shell
python -m pip install Pillow python-rapidjson freetype-py
```
Then, put the script into your resource pack's root folder and run it:
```shell
python convert_font.py default _neg -1
```
This example assumes that the resource pack has a font called `minecraft:default`, and it will then create a new font called `minecraft:default_neg` that exactly cancels out the original font.

## Full Syntax
The full format for the command is:
```shell
python convert_font.py font suffix factor [-h] [-t TARGET_PACK_FOLDER] [-f FALLBACK_PACK_FOLDER] [-u UNIHEX_MODE] [-q]
```
The meaning of each argument is:
```
font:
    Namespaced ID of original font
suffix:
    Suffix added to converted font ID
factor:
    Factor that the width of each character should be multiplied with.
-t, --target_pack_folder TARGET_PACK_FOLDER:
    Path to root of target resource pack. Defaults to working directory.
-f, --fallback_pack_folder FALLBACK_PACK_FOLDER:
    Path to root of fallback resource pack. Resources that don't exist in the target pack are looked up here instead.
-u, --unihex_mode {none,ascii,all_named,all}:
    Decides which unihex characters will be included. Defaults to ascii.
-w, --whitelist WHITELIST:
    A string containing all the characters that should still included despite not being included in the unihex mode.
-q, --quiet:
    Decides whether to show log messages.
```

So a more advanced example would be:
```shell
python convert_font.py default _neg_half -0.5 -t ./output -f ./vanilla_resource_pack -u all_named -q
```

Because the Minecraft jar found at `.minecraft/versions/<version>/<version>.jar` does not have any of the unihex characters, I recommend getting the full default font from the vanilla resource pack at the [mcmeta repo](<https://github.com/misode/mcmeta/tree/assets>).

But beware of including too many of the unihex characters: The resource pack's loading time can increase drastically when there are too many characters. This is why the script defaults to including only ascii unihex characters.
