
class CircularBufferIterator:
    def __init__(self, sequ):
        self._index = sequ.old
        self._count = 0
        self._sequ = sequ
        # print(f"__init: _index={self._index}, old={self._sequ.old}, new={self._sequ.new}")

    def __next__(self):
        nextindex = (self._index + 1) % self._sequ.cap
        if self._sequ.is_empty() or (nextindex == self._sequ.new):
            raise StopIteration

        item = self._sequ.buffer[self._index]
        self._index = nextindex
        self._count += 1
        # print(f"__next: _index={self._index}, _count={self._count}, new={self._sequ.new}, item={item.json}")
        return item


class CircularBuffer:

    def __init__(self, capacity):
        self.buffer = [None for _ in range(capacity)]
        self.new = 0
        self.old = 0
        self.size = 0
        self.cap = capacity

    def read(self):
        value = self.buffer[self.old]
        if value is None:
            raise Exception("CircularBuffer is empty")
        self.buffer[self.old] = None
        self.old = (self.old + 1) % len(self.buffer)
        self.size -= 1
        return value

    def write(self, data):
        """Non-overwriting version - on full raises exception."""
        if self.buffer[self.new] is not None:
            raise Exception("CircularBuffer is full")
        self.buffer[self.new] = data
        self.new = (self.new + 1) % self.cap
        self.size -= 1

    def overwrite(self, data):
        """Overwriting version - on full loses oldest data."""
        # The condition new == old is ambiguous, repr either full or empty.
        # We're using a size value to disambiguate this, but an alternative
        # is to reserve the entry at new==old as an always unused slot, and
        # then new+1 == old becomes 'full' while new == old is empty.
        if self.is_full() and not self.is_empty():
            self.size -= 1   # repr loss of oldest
            self.old = (self.old + 1) % self.cap
        self.buffer[self.new] = data
        self.new = (self.new + 1) % self.cap
        self.size += 1
        # print(self)

    def is_full(self):
        return self.old == self.new

    def is_empty(self):
        return self.size == 0

    def clear(self):
        self.old = self.new = 0
        self.size = 0
        for i in range(self.cap):
            self.buffer[i] = None

    def __len__(self):
        return self.size

    def capacity(self):
        return self.cap

    def __repr__(self):
        return f"CB({self.cap}): size={self.size}, new={self.new}, old={self.old}, empty={self.is_empty()}, full={self.is_full()}"

    def __str__(self):
        return f"CB({self.cap}): size={self.size}, data=..."

    def __iter__(self):
        return CircularBufferIterator(self)
