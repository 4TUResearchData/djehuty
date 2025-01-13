"""
This module is a purpose-simplified version of the 'zipfly' package.  We
recommend to use the full version: https://pypi.org/project/zipfly.

See the license comment in 'src/djehuty/web/zipfly.py' for the licensing
conditions of 'zipfly'.
"""

# Original 'zipfly' license:
# -----------------------------------------------------------------------------
# Copyright (c) 2020 Cardallot, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------

import io
import zipfile
from zipfile import ZipFile, ZIP_STORED
class LargePredictionSize (Exception):
    """Raised when Buffer is larger than ZIP64."""

class ZipflyStream (io.RawIOBase):
    """
    The RawIOBase ABC extends IOBase. It deals with
    the reading and writing of bytes to a stream. FileIO subclasses
    RawIOBase to provide an interface to files in the machine’s file system.
    """
    def __init__ (self):
        self._buffer = b""
        self._size = 0

    def writable (self):
        """Returns True to signify the stream is writable."""
        return True

    def write (self, b):
        """Procedure to write a chunk to the opened stream."""
        if self.closed:  # pylint: disable=using-constant-test
            raise RuntimeError("ZipFly stream was closed!")
        self._buffer += b
        return len(b)

    def get (self):
        """Procedure to read a chunk from the opened stream."""
        chunk = self._buffer
        self._buffer = b""
        self._size += len(chunk)
        return chunk

    def size (self):
        """Returns the current size of the stored stream."""
        return self._size


class ZipFly:
    """The core ZipFly class."""
    def __init__(self, paths=None):
        """This class implements the main ZipFly functionality."""
        self.paths = paths if paths is not None else []
        self.filesystem = "fs"
        self.arcname = "n"
        self.chunksize = 0x8000
        self._buffer_size = None

    def buffer_prediction_size (self):
        """Returns the predicted size for the Zip buffer."""
        end_of_central_directory = int("0x16", 16)
        file_offset = int("0x5e", 16) * len(self.paths)
        size_paths = 0
        for path in self.paths:
            name = self.arcname
            if not self.arcname in path:
                name = self.filesystem

            tmp_name = path[name]
            if tmp_name.startswith ("/"):
                tmp_name = tmp_name[1:len(tmp_name)]

            size_paths += (len(tmp_name.encode("utf-8")) - 1) * 2

        zs = sum([end_of_central_directory,file_offset,size_paths])
        if zs > 2147483649: # (1 << 31) + 1
            raise LargePredictionSize("File predicted to be larger than the ZIP64 limit.")

        return zs

    def generator (self):
        """Returns a generator to stream-on-the-fly."""
        stream = ZipflyStream()
        with ZipFile(stream, mode="w", compression=ZIP_STORED, allowZip64=True) as zf:
            for path in self.paths:
                if self.filesystem not in path:
                    raise RuntimeError(f"'{self.filesystem}' key is required")
                if not self.arcname in path:
                    path[self.arcname] = path[self.filesystem]
                z_info = zipfile.ZipInfo.from_file(path[self.filesystem], path[self.arcname])
                with open (path[self.filesystem], "rb") as e:
                    with zf.open (z_info, mode="w") as d:
                        for chunk in iter(lambda: e.read(self.chunksize), b""):  # pylint: disable=cell-var-from-loop
                            d.write(chunk)
                            yield stream.get()
        yield stream.get()
        self._buffer_size = stream.size()
        stream.close()

    def get_size (self):
        """Returns the current size of the buffer."""
        return self._buffer_size
