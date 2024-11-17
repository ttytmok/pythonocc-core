/*

Copyright 2020 Thomas Paviot (tpaviot@gmail.com)

This file is part of pythonOCC.

pythonOCC is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pythonOCC is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pythonOCC.  If not, see <http://www.gnu.org/licenses/>.

*/

%include <python/std_iostream.i>
%include <python/std_string.i>

// Typemaps for std::istream&
%typemap(in) std::istream& {
    if (!PyUnicode_Check($input)) {
        PyErr_SetString(PyExc_TypeError, "Input must be a string");
        return NULL;
    }
    PyObject* temp_bytes = PyUnicode_AsEncodedString($input, "UTF-8", "strict");
    if (!temp_bytes) return NULL;
    std::string data(PyBytes_AsString(temp_bytes));
    Py_DECREF(temp_bytes);
    $1 = new std::istringstream(data);
}

%typemap(freearg) std::istream& {
    delete $1;
}

// Typemaps for std::stringstream&
%typemap(in) std::stringstream& {
    if (!PyUnicode_Check($input)) {
        PyErr_SetString(PyExc_TypeError, "Input must be a string");
        return NULL;
    }
    PyObject* temp_bytes = PyUnicode_AsEncodedString($input, "UTF-8", "strict");
    if (!temp_bytes) return NULL;
    std::string data(PyBytes_AsString(temp_bytes));
    Py_DECREF(temp_bytes);
    $1 = new std::stringstream(data);
}

%typemap(freearg) std::stringstream& {
    delete $1;
}

// Typemap for std::ostream&
%typemap(argout) std::ostream& OutValue {
    std::ostringstream* oss = dynamic_cast<std::ostringstream*>(&$1);
    if (!oss) {
        PyErr_SetString(PyExc_RuntimeError, "argout typemap expects std::ostringstream");
        return;
    }
    PyObject* py_str = PyUnicode_FromString(oss->str().c_str());
    if (!py_str) return;

    if (!$result || $result == Py_None) {
        $result = py_str;
    } else {
        if (!PyTuple_Check($result)) {
            PyObject* old_result = $result;
            $result = PyTuple_New(1);
            PyTuple_SetItem($result, 0, old_result);
        }
        PyTuple_SetItem($result, PyTuple_Size($result), py_str);
    }
}

// Typemap for std::ostream& with default output
%typemap(in, numinputs=0) std::ostream& OutValue (std::ostringstream temp) {
    $1 = temp;
}