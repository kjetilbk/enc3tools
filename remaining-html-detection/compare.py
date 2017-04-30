import argparse
import re
import cld2full as cld
from collections import OrderedDict
import xml.etree.cElementTree as cet
import time
import nltk

html_entities = eval(open("html-entities.lst", "r").read())

def read_document(f, documents):
    doc = ""
    url = ""
    while True:
        line = f.readline()
        if line == "":
            return False
        doc += line
        if line.startswith("<doc"):
            match = re.match(r'<doc (?:\w|\"|\d|=|\s)*url=\"(.+?)\"', line)
            url = match.group(1)
        elif line.startswith("</doc>"):
            break
    documents.append((url, doc))
    return True

def read_corpus(corpus):
    f = open(corpus, "r")
    documents = []
    hasNext = True
    while hasNext:
        hasNext = read_document(f, documents)
    return sorted(documents, key=lambda k: k[0])

def parse_corpus(corpus):
    docs = []
    doc = ""
    err = 0
    for event, elem in cet.iterparse(corpus):
        if elem.tag == "metrics":
            if not elem.tail == None:
                doc += elem.tail
        if elem.tag == "doc":
            url = elem.attrib['url']
            #try:
            docs.append((url, doc.encode("utf-8")))
            #except:
                #err += 1
            doc = ""
            elem.clear()
    print err
    return sorted(docs, key=lambda k: k[0])


def read_wet_header_and_skip_info(f):
    info = f.readline()
    url = ""
    length = 0
    if info.split()[1] == "warcinfo":
        while True:
            line = f.readline()
            if line.startswith("WARC/1.0"):
                return read_wet_header_and_skip_info(f)
    else:
        url = f.readline().split()[1]
        while True:
            line = f.readline()
            if line.startswith("Content-Length"):
                length = int(line.split()[1])
            elif not (line.startswith("WARC") or line.startswith("Content")):
                return (url, length)

def read_wet_doc(f, documents):
    doc = ""
    url = ""
    while True:
        line = f.readline()
        if line.startswith("WARC/1.0"):
            url, length = read_wet_header_and_skip_info(f)
            doc = f.read(length)
            documents.append((url, doc))
            return True
        elif line == "":
            return False
    return True

def read_wet(wet):
    f = open(wet, "r")
    documents = []
    hasNext = True
    while hasNext:
        hasNext = read_wet_doc(f, documents)
    return sorted(documents, key=lambda k: k[0])

def alt_wet(wet):
    f = open(wet, "r")
    docs = []
    doc = ""
    while True:
        line = f.readline()
        if line.startswith("WARC/1.0"):
            url, length = read_wet_header_and_skip_info(f)
            if not doc.strip() == "":
                docs.append((url, unicode(doc, encoding="utf-8").encode("utf-8")))
                doc = ""
        elif line == "":
            return sorted(docs, key=lambda k: k[0])
        else:
            doc += line

def add_langs(doc, langs, langdocs, text=True):
    success, length, languages = cld.detect(doc, text)
    for lang in languages:
        name, code, prc, score = lang
        langs[name] = langs.get(name, 0.0) + length*prc/100
        if prc > 0:
            langdocs[name] = langdocs.get(name, 0) + 1
    return length
        

def print_results(distr, cnt):
    distr = OrderedDict(sorted(distr.items(), key=lambda t: t[1], reverse=True))
    output = [["Language", "Doc #", "Ratio"]]
    for entry in distr:
        output.append([entry, distr[entry], float(distr[entry])/float(cnt)])
    col_width = max(len(str(word)) for row in output for word in row) + 2
    result_string = ""
    for row in output:
        result_string += "".join(str(word).ljust(col_width) for word in row) + "\n"
    return result_string

from HTMLParser import HTMLParser
from collections import defaultdict

from multiprocessing import Process, Value, Queue


def find_html_tags(docs, progress, results, tagdicts, avail, num, idx):
    tags = defaultdict(int)
    entities = defaultdict(int)
    ntagdocs = defaultdict(int)
    nentitydocs = defaultdict(int)
    ntags = {}
    nentities = {}
    class MyHTMLParser(HTMLParser):
        def tag_is_relevant(self, tag):
            tags = ['a', 'abbr', 'acronym', 'address', 'applet', 'area',
                    'aside', 'audio', 'b', 'base', 'basefont', 'bdi',
                    'bdo', 'big', 'blockquote', 'body', 'br', 'button',
                    'canvas', 'caption', 'center', 'cite', 'code', 'col',
                    'colgroup', 'datalist', 'dd', 'del', 'details', 'dfn',
                    'dialog', 'dir', 'div', 'dl', 'dt', 'em', 'embed',
                    'fieldset', 'figcaption', 'figure', 'font', 'footer', 
                    'form', 'frame', 'frameset', 'h1', 'h2', 'h3', 'h4', 'h5',
                    'h6', 'head', 'header', 'hr', 'html', 'i', 'iframe', 'img',
                    'input', 'ins', 'kbd', 'keygen', 'label', 'legend', 'li',
                    'link', 'main', 'map', 'mark', 'menu', 'menuitem', 'meta',
                    'meter', 'nav', 'noframes', 'noscript', 'object', 'ol',
                    'optgroup', 'option', 'output', 'p', 'param', 'pre', 'progress',
                    'q', 'rp', 'rt', 'ruby', 's', 'samp', 'script', 'section',
                    'select', 'small', 'source', 'span', 'strike', 'strong', 'style',
                    'sub', 'summary', 'sup', 'table', 'tbody', 'td', 'textarea',
                    'tfoot', 'th', 'thead', 'time', 'title', 'tr', 'track', 'tt',
                    'u', 'ul', 'var', 'video', 'wbr']
            return tag in tags

        def entity_is_relevant(self, entity):
            global html_entities
            return entity in html_entities

        def handle_starttag(self, tag, attrs):
            if self.tag_is_relevant(tag):
                tags[tag] += 1
                ntags[0] += 1
        
        def handle_entityref(self, name):
            if self.entity_is_relevant(name):
                entities[name] += 1
                nentities[0] += 1

    parser = MyHTMLParser()
    local_cnt = 0
    cnt = 0
    for doc in docs:
        ntags[0] = 0
        nentities[0] = 0
        if local_cnt % 100 == 0:
            available = avail.get()
            if available > 0 and len(docs)-local_cnt > 150:
                results.put((tags, entities))
                tagdicts.put((ntagdocs, nentitydocs))
                avail.put(available-1)
                resultcnt = num.get()
                num.put(resultcnt+2)
                remaining = docs[local_cnt:]
                new_idx1 = str(idx) + "(1)"
                new_idx2 = str(idx) + "(2)"
                p_one = Process(target=find_html_tags, args=(remaining[0:len(remaining)/2],
                                                             progress, results, tagdicts,
                                                             avail, num, new_idx1))
                p_two = Process(target=find_html_tags, args=(remaining[len(remaining)/2:],
                                                             progress, results, tagdicts,
                                                             avail, num, new_idx2))
                #print "Process finished. Split another in two. avail: ", available, " num: ", resultcnt
                p_one.start()
                p_two.start()
                return tags
            avail.put(available)
        err = 0
        url, txt = doc
        try:
            parser.feed(txt)
        except:
            err = 1
        ntagdocs[url] = ntags[0]
        nentitydocs[url] = nentities[0]
        cnt, errs = progress.get()
        if cnt % 5000 == 0:
            print "cnt, errs:", cnt, errs
        #if local_cnt % 5000 == 0:
            #print "index, cnt: ", idx, local_cnt
            #print "\tremaining: ", len(docs)-local_cnt
        cnt += 1
        local_cnt += 1
        progress.put((cnt, errs+err))
    results.put((tags, entities))
    tagdicts.put((ntagdocs, nentitydocs))
    avail.put(avail.get()+1)
    return tags

def merge_results(result):
    procs = len(result)
    print "Merging results..."
    merged = result[0]
    for i in xrange(1, procs):
        p_res = result[i]
        for key, value in p_res.items():
            if key not in merged:
                merged[key] = p_res[key]
            else:
                merged[key] = merged[key] + p_res[key]
    print "Results merged"
    return merged

def merge_dicts(dicts):
    merged = dicts[0]
    for i in xrange(1, len(dicts)):
        for key, value in dicts[i][0].items():
            merged[0][key] = value
        for key, value in dicts[i][1].items():
            merged[1][key] = value
    return merged

def calc_std_dev(d):
    s = 0.0
    count = 0
    for key, value in d.items():
        s += value
        if not value == 0:
            count += 1
    mean = s/len(d)
    diffsum = 0.0
    for key, value in d.items():
        diff = (value - mean) ** 2
        diffsum += diff
    variance = diffsum / len(d)
    stddev = variance ** (0.5)
    return (s, count, mean, stddev)

def html_tags_parallell(docs, procs=1):
    final_tags = []
    final_entities = []
    tagsandentities = []
    total_length = len(docs)
    progress = Queue()
    progress.put((0, 0))
    results = Queue()
    avail = Queue()
    tagdicts = Queue()
    avail.put(0)
    num = Queue()
    num.put(procs)
    begin = 0
    end = len(docs) / procs
    idx = 0
    print "Started threads"
    for i in xrange(procs):
        idx += 1
        p_docs = docs[begin:end]
        p = Process(target=find_html_tags, args=(p_docs, progress,
                                                 results, tagdicts, avail,
                                                 num, idx))
        p.start()
        begin = end
        end = end + len(docs) / procs
        if i == procs - 2:
            end = len(docs)
    while True:
        prog, errs = progress.get()
        if prog == total_length:
            break
        progress.put((prog, errs))
    number = num.get()
    for i in xrange(number):
        tags, entities = results.get()
        final_tags.append(tags)
        final_entities.append(entities)
        tagsandentities.append(tagdicts.get())
    print "THREADS MERGED"
    merged_tags = merge_results(final_tags)
    merged_entities = merge_results(final_entities)
    m_dicts = merge_dicts(tagsandentities)
    ntagdocs, nentitydocs = m_dicts
    return (merged_tags, merged_entities, ntagdocs, nentitydocs)

def format_parse_result(html, headline):
    s = 0.0
    for key, value in html.items():
        s += value
    distr = OrderedDict(sorted(html.items(), key=lambda t: t[1], reverse=True))
    output = [[headline, "Doc #", "Ratio"]]
    for entry in distr:
        output.append([entry, html[entry], float(html[entry])/float(s)])
    col_width = max(len(str(word)) for row in output for word in row) + 2
    result_string = ""
    for row in output:
        result_string += "".join(str(word).ljust(col_width) for word in row) + "\n"
    return result_string

def output_parse_result(html, distr, headline, out):
    result_string = format_parse_result(html, headline)
    sum, count, mean, stddev = calc_std_dev(distr)
    o = open(out, "w+")
    o.write(result_string)
    o.write("\n\n")
    o.write("Total no. of " + headline + ": " + str(sum) + "\n")
    o.write("Number of documents with " + headline + "s: " + str(count))
    o.write("Average per document: " + str(mean)+ "\n")
    o.write("Standard deviation: " + str(stddev) + "\n")
    o.close()

def get_intersection(corpus, wet):
    i = 0
    j = 0
    similar = []
    while i < len(corpus) and j < len(wet):
        corpurl = corpus[i][0].strip()
        weturl = wet[j][0].strip()
        if corpurl == weturl:
            i += 1
            j += 1
            similar.append(wet[j])
        elif corpurl > weturl:
            j += 1
        elif corpurl < weturl:
            i += 1
    return similar

def perform_lang_id(docs, o, dtype):
    langs = {}
    langdocs = {}
    errors = 0
    total_length = 0
    for doc in docs:
        try:
            total_length += add_langs(doc[1], langs, langdocs, text=True)
        except:
            errors += 1
    print "Counted language distribution of", len(docs), dtype
    o.write(dtype + ": " +str(len(docs))+"\n")
    o.write("# UTF-8 Errors: "+str(errors)+"\n")
    o.write(print_results(langs, total_length)+"\n")
    o.write("\n"+"How many docs was language l seen in?:\n")
    s = 0
    for key, value in langdocs.items():
        s += value
    o.write(print_results(langdocs, s))
    o.write("\n\n")

def count_langs_write_to_file(corpus_documents, wet_documents, intersection, output):
    o = open(output, "w+")
    perform_lang_id(corpus_documents, o, "texrex documents")
    perform_lang_id(wet_documents, o, "WET documents")
    perform_lang_id(intersection, o, "documents from WET that is also in texrex")
    o.close()

def count_tokens(docs, dtype, o):
    tokens = {}
    errors = 0
    cnt = 0
    for url, doc in docs:
        try:
            tokens[url] = len(nltk.word_tokenize(doc))
        except:
            errors += 1
    sum, count, mean, stddev = calc_std_dev(tokens)
    o.write(dtype + " tokens:\n")
    o.write("total amount: " + str(sum) + "\n")
    o.write("average per doc: " + str(mean) + "\n")
    o.write("standard deviation: " + str(stddev) + "\n")
    o.write("Encoding errors: " + str(errors) + "\n")

def write_token_amount_to_file(corpus_documents, wet_documents, intersection, output):
    o = open("token_"+output, "w+")
    count_tokens(corpus_documents, "texrex documents", o)
    count_tokens(wet_documents, "WET documents", o)
    count_tokens(intersection, "documents from WET that is also in texrex", o)

def perform_count_and_output(docs, processes, outputfilename):
    tags, entities, tag_distr, entity_distr = html_tags_parallell(docs, procs=processes)
    output_parse_result(tags, tag_distr, "Tag", "tag_"+outputfilename)
    output_parse_result(entities, entity_distr, "Entity", "entity_"+outputfilename)

def compare(wet, corpus, output, procs):
    corpus_docs = parse_corpus(corpus)
    print "Read corpus"
    wet_documents = alt_wet(wet)
    print "Read WET file"
    wet_intersection = get_intersection(corpus_docs, wet_documents)
    wet_out = "wet_" + output
    intersection_out = "intersection_wet_" + output
    tex_out = "texrex_" + output
    perform_count_and_output(wet_documents, procs, wet_out)
    perform_count_and_output(corpus_docs, procs, tex_out)
    perform_count_and_output(wet_intersection, procs, intersection_out)
    count_langs_write_to_file(corpus_docs, wet_documents, wet_intersection, "lang_"+output)
    write_token_amount_to_file(corpus_docs, wet_documents, wet_intersection, output)

def main():
    parser = argparse.ArgumentParser(description="Compare a WET file and a corpus created from the corresponding WARC file")
    parser.add_argument("wet", help="the WET file to read")
    parser.add_argument("corpus", help="the corpus file to be read")
    parser.add_argument("--output", "-o", help="a filename for the different output stats files", default="compare.out")
    parser.add_argument("--procs", "-p", help="how many processors can be run in parallel", default=12)
    args = parser.parse_args()
    compare(args.wet, args.corpus, args.output, args.procs)

if __name__ == "__main__":
    main()
