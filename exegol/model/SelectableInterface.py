class SelectableInterface:
    """Generic class used to select objects in the user TUI"""

    def getKey(self) -> str:
        """Universal unique key getter"""
        raise NotImplementedError

    def __eq__(self, other):
        """Generic '==' operator overriding matching object key"""
        return other == self.getKey()
