class SelectableInterface:
    """Generic class used to select objects in the user TUI"""

    def getKey(self) -> str:
        """Universal unique key getter"""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        """Generic '==' operator overriding matching object key"""
        if type(other) is str:
            return other == self.getKey()
        elif isinstance(other, SelectableInterface):
            return other.getKey() == self.getKey()
        raise NotImplementedError
