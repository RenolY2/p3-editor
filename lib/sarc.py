from io import BytesIO

import time

from .yaz0 import decompress, read_uint32, read_uint16


def stringtable_get_name(f, stringtable_offset, offset):
    current = f.tell()
    f.seek(stringtable_offset+offset)

    stringlen = 0
    while f.read(1) != b"\x00":
        stringlen += 1

    f.seek(stringtable_offset+offset)

    filename = f.read(stringlen)
    try:
        decodedfilename = filename.decode("shift-jis")
    except:
        print("filename", filename)
        print("failed")
        raise
    f.seek(current)

    return decodedfilename

class File(BytesIO):
    def __init__(self, filename, attributes=0):
        super().__init__()

        self.name = filename
        self.attributes = attributes

    @classmethod
    def from_file(cls, filename, f):
        file = cls(filename)

        file.write(f.read())
        file.seek(0)

        return file

    @classmethod
    def from_node(cls, filename, attributes, f, offsetstart, offsetend):
        file = cls(filename, attributes)
        curr = f.tell()
        f.seek(offsetstart)
        file.write(f.read(offsetend-offsetstart))
        file.seek(0)
        f.seek(curr)

        return file


class SARCArchive(object):
    def __init__(self):
        self.files = {}
        self.unnamed_files = []

    @classmethod
    def from_file(cls, f):
        newarc = cls()
        print("ok")
        header = f.read(4)

        if header == b"Yaz0":
            # Decompress first
            print("Yaz0 header detected, decompressing...")
            start = time.time()
            tmp = BytesIO()
            f.seek(0)
            decompress(f, tmp)
            #with open("decompressed.bin", "wb") as g:
            #    decompress(f,)
            f = tmp
            f.seek(0)

            header = f.read(4)
            print("Finished decompression.")
            print("Time taken:", time.time() - start)

        if header == b"SARC":
            pass
        else:
            raise RuntimeError("Unknown file header: {} should be Yaz0 or SARC".format(header))

        header_size = read_uint16(f)
        assert read_uint16(f) == 0xFEFF # BOM: Big endian
        size = read_uint32(f)

        data_offset = read_uint32(f)
        version = read_uint16(f)
        reserved = read_uint16(f)

        print("Archive version", hex(version), "reserved:", reserved)


        # SFAT header
        sfat = f.read(4)
        assert sfat == b"SFAT"
        sfat_header_size = read_uint16(f)
        assert sfat_header_size == 0xC
        node_count = read_uint16(f)
        hash_key = read_uint32(f)

        nodes = []
        for i in range(node_count):
            filehash = read_uint32(f)
            fileattr = read_uint32(f)
            node_data_start = read_uint32(f)
            node_data_end = read_uint32(f)
            nodes.append((fileattr, node_data_start, node_data_end))

        # String table
        assert f.read(4) == b"SFNT"
        assert read_uint16(f) == 0x8
        read_uint16(f) # reserved

        string_table_start = f.tell()

        for fileattr, start, end in nodes:
            if fileattr & 0x01000000:
                stringoffset = (fileattr & 0xFFFF) * 4
                path = stringtable_get_name(f, string_table_start, stringoffset)
            else:
                path = None

            file = File.from_node(path, fileattr, f, data_offset+start, data_offset+end)
            if path is not None:
                assert path not in newarc.files
                newarc.files[path] = file
            else:
                newarc.unnamed_files.append(file)

        return newarc


if __name__ == "__main__":
    with open("mapA_text.szs", "rb") as f:
        sarc = SARCArchive.from_file(f)

    for path, file in sarc.files.items():
        with open(path, "wb") as f:
            f.write(file.getvalue())