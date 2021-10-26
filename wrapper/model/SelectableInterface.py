class SelectableInterface:
    def getKey(self):
        """Universal unique key getter"""
        raise NotImplementedError

    def __eq__(self, other):
        """Generic '==' operator overriding matching object key"""
        return other == self.getKey()
