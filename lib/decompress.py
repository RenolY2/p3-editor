import sys 
from yaz0 import decompress

inputfile = sys.argv[1]

with open(inputfile, "rb") as f:
    with open(inputfile+".bin", "w+b") as g:
        decompress(f, g)