wps = [("EN-WS-353-ALL.txt", 10), ("EN-MC-30.txt", 4), ("EN-RG-65.txt", 4), ("EN-SCWS.txt", 10), ("EN-RW-STANFORD.txt", 10), ("EN-SIMLEX-999.txt", 10), ("EN-YP-130.txt", 4), ("EN-VERB-143.txt", 1)]

wordpairs = {}
for wp in wps:
    filename, maxscore = wp
    with open(filename, "r") as f:
        for line in f:
            pairsscore = line.strip().split()
            if pairsscore[0] < pairsscore[1]:
                wp1 = pairsscore[0]
                wp2 = pairsscore[1]
            else:
                wp1 = pairsscore[1]
                wp2 = pairsscore[0]
            score = float(pairsscore[2])/maxscore
            candidate = (wp1, wp2)
            if (not candidate in wordpairs) or score < wordpairs[candidate]:
                wordpairs[candidate] = score
for a, b in sorted(wordpairs.iteritems(), key=lambda lst: lst[1], reverse=True):
    print a[0], a[1], b
