import argparse
import glob
import re
import gzip
from xml.sax.saxutils import unescape

def read_documents(xml):
    doc = ""
    docs = []
    err = 0
    docoffset = 0
    skipline = False
    actualtext = False
    while True:
        try:
            potentialoffset = xml.tell()
            rline = xml.readline()
            line = rline.decode("utf-8")
            if line == '':
                break
            if line.startswith("<doc"):
                docoffset = potentialoffset
            if skipline or \
                    line.startswith("<doc") or \
                    line.startswith("<meta") or \
                    line.startswith("</div>") or \
                    line.startswith("</title>") or \
                    line.startswith("</description>") or \
                    line.startswith("</keywords>"):
                skipline = False
                actualtext = False
                continue
            elif line.startswith("<title>") or \
                    line.startswith("<description>") or \
                    line.startswith("<keywords>"):
                skipline = True
                continue
            elif line.startswith("<div"):
                res = re.search(u'bpv=\"(-?\d\.?\d*(?:E-\d)?)\"', line)
                if res == None:
                    err += 1
                    skipline = True
                    continue
                if float(res.group(1)) < 0.5:
                    actualtext = True
            elif line.startswith("</doc"):
                docs.append((doc, docoffset))
                doc = ""
            else:
                if actualtext:
                    unescaped = unescape(line, {"&apos;": "'", "&quot;": '"'})
                    final = re.sub("(<doc.*>)", "", unescaped)
                    doc += final + "\n"
        except UnicodeDecodeError:
            print("Unicode error in file", xml.name,"at",xml.tell())
    print("XML errors: ", err)
    return docs

def open_gzipped(filename):
    f = gzip.open(filename, "rb", encoding='utf-8')
    return f

def open_uncompressed(filename):
    f = open(filename, "rb")
    return f

def docstofile(prefix, originfile, docs, startidx, endidx):
    docfilename = prefix + ".txt"
    metafilename = prefix + ".meta"
    with open(docfilename, "a+") as f, open(metafilename, "a+") as m:
        for doc, docoffset in docs[startidx:endidx]:
            f.write(doc + "\f")
            m.write(originfile + "\t" + str(docoffset) + "\n")

def write_docs(prefix, originfile, docs, last_doc, docsperfile):
    count, fileidx = last_doc
    if count is not None:
        filename = filename = prefix + "."+str(fileidx)
        docstofile(filename, originfile, docs, 0, docsperfile - count)
        docs = docs[docsperfile-count:]
        fileidx += 1
    else:
        fileidx = 1
    filecount = int(len(docs)/docsperfile)
    for i in range(filecount):
        filename = prefix + "."+str(fileidx)
        docstofile(filename, originfile, docs, i*docsperfile, (i+1)*docsperfile)
        fileidx += 1
    if len(docs) % docsperfile > 0:
        filename = prefix + "."+str(fileidx)
        docstofile(filename, originfile, docs, filecount*docsperfile, len(docs))
    return (docsperfile - (len(docs) % docsperfile), fileidx)

def extract_text(path, is_zipped, n, output):
    files = glob.glob(path)
    last_doc = (None, 0)
    for z in files:
        print("processing", z)
        try:
            if is_zipped:
                xml = open_gzipped(z)
            else:
                xml = open_uncompressed(z)
            docs = read_documents(xml)
            last_doc = write_docs(output, z, docs, last_doc, n)
        except MemoryError:
            print("MemoryError, could not read:", z)
        except IOError as e:
            with open("error-files-xml2txt.txt", "a+") as out:
                out.write("FATAL ERROR. File: " + z + ".\nError: " + str(e) + "\n\n")

def main():
    parser = argparse.ArgumentParser(description="Extract non-boilerplate text from XML corpus files as produced by texrex.")
    parser.add_argument("path", help="The path to the corpus files (accepts wildcards within \"double quotes\")")
    parser.add_argument("--gzip", "-g", help="Tell the program whether the input is compressed.", action="store_true", default=False)
    parser.add_argument("--output", "-o", help="prefix of output, text will be stored as prefix.[index].txt, meta files will be stored as prefix.[index].meta", default="corp")
    parser.add_argument("--ndocs", "-n", help="Number of web documents to store per file before starting a new one", type=int, default=10000)
    args = parser.parse_args()
    extract_text(args.path, args.gzip, args.ndocs, args.output)

if __name__ == "__main__":
    main()
