Compages, structuring/unstructuring library
===========================================

Overview
--------

``compages`` is a library converting data between well-typed representation (that's what a program typically operates with) and a combination of built-in types (suitable for serializing into some storage/transfer format).


Similar libraries
-----------------

- `cattrs <https://pypi.org/project/cattrs/>`_ (which is very similar to ``compages``, and is the source of the terms "structure/unstructure")
- `marshmallow <https://pypi.org/project/marshmallow/>`_
- `pydantic <https://pypi.org/project/pydantic/>`_
- `maat <https://pypi.org/project/Maat2/>`_
- `mashumaro <https://pypi.org/project/mashumaro/>`_
- `desert <https://pypi.org/project/desert/>`_


Introduction
------------

Two central concepts of the library are *structured* and *unstructured* representation of data.

The structured representation is what you normally operate with in your program, consisting of structures containing type information for their fields.

The unstructured representation would generally be something you can pass to a serialization library, for example JSON or MessagePack.
The specific set of builtins can be different depending on the planned usage; JSON does not accept ``bytes``, while MessagePack is fine with ``bytes`` but does not support dictionaries.

In general, what to consider structured and unstructured representations is up to you, but there is one important asymmetry: the structured representation is the ethalon against which the data is matched, both during structuring and unstructuring.
So, you structure into a specific type and unstructure from a specific type (often would coincide with what ``type()`` returns, but not always).


Structuring
-----------

Structuring can be viewed as (and very often is) deserialization.
A :py:class:`Structurer` object takes a number of handlers that determine how to structure some serialized data into a specific type, and applies them according to a simple routing algorithm.
If the user wants to structure into type ``T``, the order of actions is the following:
- If there is a handler registered for ``T``, call it;
- If ``T`` is a ``typing.NewType``, and there is a handler registered for its supertype, call it;
- If ``T`` is a generic (that is, has a non-``None`` ``typing.get_origin()``), and there is a handler registered for its ``get_origin()``, call it;
- Go through the list of :py:class:`PredicateStructureHandler` objects (which was supplied on initialization, along with regular handlers) until one can be applied, and call it.

If no handlers were called by this time, an error is raised.
If a handler was called but returned an error, no more attempts to find another handler are made; the error is raised as well.

A handler receives the :py:class:`Structurer` object itself, the type ``T``, and the value that is being structured.
Therefore it can call :py:meth:`Structurer.structure_into` recursively if needed.
Handlers for generic origin types like ``list`` or ``dict``, or structure description types like dataclasses, work this way.

The errors handlers raise may contain multiple nested errors with the corresponding paths for disambiguation; for example, a dataclass structurer will collect and return structuring errors for each field.
Printing out the error will display the tree-like structure of errors and paths in the data structure at which they originated.



.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   changelog


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

