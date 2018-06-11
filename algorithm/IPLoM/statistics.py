class statistics:
    def __init__(self,path=None):
        self.path=path
        print(path)
        self.file =open(path,'r')
    def nbrLines(self):
        return sum(1 for line in self.file)
