from PIL import Image
import freetype
import zipfile
import rapidjson
import os
import argparse

class WidthConverter:
    @classmethod
    def main(cls):
        """
        Runs if the file was called from the CLI.
        """
        parser = argparse.ArgumentParser(
            description="Converts a font file to a new font file that replaces each character with a space that has the width of the same character in the original font but multiplied by a given factor."
        )
        
        parser.add_argument(
            "font",
            help="Namespaced ID of original font."
        )
        parser.add_argument(
            "suffix",
            help="Suffix added to converted font."
        )
        parser.add_argument(
            "factor",
            help="Factor that the width of each character should be multiplied with.",
            type=float
        )
        parser.add_argument(
            "-t",
            "--target_pack_folder",
            help="Path to root of target resource pack. Defaults to working directory."
        )
        parser.add_argument(
            "-f",
            "--fallback_pack_folder",
            help="Path to root of fallback resource pack. Resources that don't exist in the target pack are looked up here instead."
        )
        parser.add_argument(
            "-u",
            "--unihex_mode",
            help="Decides which unihex characters will be included. Defaults to ascii.",
            choices=["none", "ascii", "all_named", "all"]
        )
        parser.add_argument(
            "-q",
            "--quiet",
            help="Decides whether to show log messages.",
            action="store_true"
        )
        
        args = parser.parse_args()
        
        converter = cls(
            args.suffix,
            args.factor,
            args.target_pack_folder,
            args.fallback_pack_folder,
            args.unihex_mode,
            not args.quiet
        )
        
        converter.convert_font(args.font)
        if converter.verbose:
            print("Done!")

    def __init__(self,
                 suffix,
                 width_factor,
                 target_pack_folder=None,
                 fallback_pack_folder=None,
                 unihex_mode=None,
                 verbose=True):
        self.suffix = suffix
        
        self.width_factor = width_factor
        
        if target_pack_folder is None:
            target_pack_folder = os.getcwd()
        self.target_pack_folder = target_pack_folder
        self.fallback_pack_folder = fallback_pack_folder
        
        if unihex_mode is None:
            unihex_mode = "ascii"
        self.unihex_mode = unihex_mode
        
        self.verbose = verbose
        
    
    def convert_font(self, font_id):
        """
        Converts the font with the given ID to a new font with the characters replaced by spaces.
        """
        new_font_id = font_id + self.suffix
        if self.verbose:
            print(f'Converting font "{font_id}" to "{new_font_id}"')
        old_path = self.get_font_path(font_id)
        new_path = self.get_font_path(new_font_id, mode="w")
        
        with open(old_path) as f:
            old_providers = rapidjson.load(f, parse_mode=rapidjson.PM_TRAILING_COMMAS)["providers"]
        space_providers = []
        other_providers = []
        for old_provider in old_providers:
            new_provider = self.convert_provider(old_provider)
            if not new_provider:
                continue
            self.assure_integers(new_provider)
            if "filter" in old_provider:
                new_provider["filter"] = old_provider["filter"]
                other_providers.append(new_provider)
            elif new_provider["type"] == "space":
                space_providers.append(new_provider)
            else:
                other_providers.append(new_provider)
        
        while len(space_providers) > 1:
            to_merge = space_providers.pop()
            space_providers[-1]["advances"].update(to_merge["advances"])
        
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        with open(new_path, "w+", encoding="utf-8") as f:
            rapidjson.dump({
                "providers": other_providers + space_providers
            }, f, ensure_ascii=False)
        
        return new_font_id

    def assure_integers(self, provider):
        """
        If the given provider is of type space, convert all whole-numbered advances to integers.
        """
        if provider["type"] != "space":
            return
        advances = provider["advances"]
        for k in advances:
            if advances[k].is_integer():
                advances[k] = int(advances[k])
    
    def convert_provider(self, provider):
        """
        Takes a provider and returns its equivalent space provider.
        """
        provider_type = provider["type"]
        if provider_type == "reference":
            return self.convert_reference_provider(provider)
        if provider_type == "space":
            return self.convert_space_provider(provider)
        if provider_type == "ttf":
            return self.convert_ttf_provider(provider)
        if provider_type == "bitmap":
            return self.convert_bitmap_provider(provider)
        if provider_type == "unihex":
            return self.convert_unihex_provider(provider)
        
        raise Exception(f'Unknown provider type "{provider_type}"')

    def convert_reference_provider(self, old_provider):
        font_id = old_provider["id"]
        new_font_id = self.convert_font(font_id)
        return {
            "type": "reference",
            "id": new_font_id
        }

    def convert_ttf_provider(self, old_provider):
        file = old_provider["file"]
        if self.verbose:
            print(f'Parsing file "{file}"')
        file = self.get_resource_path(file, "font")
        size = old_provider.get("size", 11)
        oversample = old_provider.get("oversample", 1)
        skip = old_provider.get("skip", "")
        if isinstance(skip, list):
            skip = "".join(skip)
        skip = set(skip)
        face = freetype.Face(file)
        i = size * oversample
        face.set_pixel_sizes(i, i)
        
        advances = {}
        for code, idx in face.get_chars():
            char = chr(code)
            if char in skip:
                continue
            face.load_glyph(idx, 4194312)
            advance = face.glyph.advance.x / 64 / oversample
            advances[char] = advance * self.width_factor
        return {
            "type": "space",
            "advances": advances
        }

    def convert_space_provider(self, old_provider):
        advances: dict = old_provider["advances"]
        return {
            "type": "space",
            "advances": {
                key: value * self.width_factor
                for key, value in advances.items()
            }
        }

    def convert_bitmap_provider(self, old_provider):
        chars = old_provider["chars"]
        file = old_provider["file"]
        if self.verbose:
            print(f'Parsing file "{file}"')
        file = self.get_resource_path(file, "textures")
        height = old_provider.get("height", 8)
        img = Image.open(file).convert("RGBA")
        result = {}
        num_rows = len(chars)
        for y, line in enumerate(chars):
            num_cols = len(line)
            char_height = img.height // num_rows
            char_width = img.width // num_cols
            for x, char in enumerate(line):
                if char in "\u0000 ":
                    continue
                cursor_x = x * char_width
                cursor_y = y * char_height
                for i in range(char_width-1, -1, -1):
                    scan = self.scan_bitmap_col(img, cursor_x + i, cursor_y, char_height)
                    if scan:
                        width = i + 1
                        break
                else:
                    width = 0
                width = width * height / char_height
                result[char] = (int(0.5 + width) + 1) * self.width_factor
        return {
            "type": "space",
            "advances": result
        }

    def scan_bitmap_col(self, img, start_x, start_y, height):
        for i in range(height):
            if img.getpixel((start_x, start_y + i))[-1] != 0:
                return True
        return False

    def convert_unihex_provider(self, old_provider):
        if self.unihex_mode == "none":
            return None
        file = old_provider["hex_file"]
        if self.verbose:
            print(f'Parsing file "{file}"')
        file = self.get_resource_path(file, "", "")
        zip = zipfile.ZipFile(file)
        for zipinfo in zip.infolist():
            if zipinfo.filename.endswith(".hex"):
                hex = zip.open(zipinfo).read().decode("utf-8")
        overrides = [
        ]
        for override in old_provider.get("size_overrides", []):
            min_code = ord(override["from"])
            max_code = ord(override["to"])
            diff = override["right"] - override["left"]
            width = 0 if min_code==max_code==0 else diff + 1
            overrides.append((min_code, max_code, width))
        advances = {}
        for line in hex.splitlines():
            code, img = line.split(":")
            code = int(code, 16)
            if self.unihex_mode == "ascii" and code > 256:
                continue
            for min_code, max_code, override_width in overrides:
                if min_code <= code <= max_code:
                    width = override_width
                    break
            else:
                if self.unihex_mode == "all_named" and code > 256:
                    continue
                width = self.read_hex_bitmap(img)
            advances[chr(code)] = (int(0.5 * width) + 1) * self.width_factor
        if len(advances)==0:
            return None
        return {
            "type": "space",
            "advances": advances
        }

    def read_hex_bitmap(self, img):
        """
        Returns how many pixels a unihex character is based on its hexadecimal bitmap.
        """
        row_len = len(img) // 16
        min_pixel = row_len*4
        max_pixel = -1
        for i in range(16):
            row = int(img[i*row_len:(i+1)*row_len], 16)
            if row==0:
                continue
            low = (row & -row).bit_length()
            min_pixel = min(low, min_pixel)
            high = row.bit_length()
            max_pixel = max(high, max_pixel)
        return 0 if max_pixel==-1 else max_pixel - min_pixel + 1

    def get_resource_path(self, resource_id, resource_type, extension="", mode="r"):
        """
        Returns the file path for a given namespaced ID for a general resource.
        """
        if ":" in resource_id:
            namespace, location = resource_id.split(":")
        else:
            namespace, location = "minecraft", resource_id
        location = location + extension
        path = os.path.join("assets", namespace, resource_type, *location.split("/"))
        target_path = os.path.join(self.target_pack_folder, path)
        if mode=="w" or not self.fallback_pack_folder or os.path.isfile(target_path):
            return target_path
        else:
            return os.path.join(self.fallback_pack_folder, path)
        

    def get_font_path(self, font_id, mode="r"):
        """
        Returns the file path for a given namespaced ID for a font json file.
        """
        return self.get_resource_path(font_id, "font", ".json", mode=mode)

if __name__=="__main__":
    WidthConverter.main()
