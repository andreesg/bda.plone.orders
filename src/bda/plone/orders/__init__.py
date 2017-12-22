# -*- coding: utf-8 -*-
from zope.i18nmessageid import MessageFactory
message_factory = MessageFactory('bda.plone.orders')

from Products.CMFPlone.utils import safe_unicode

def safe_encode(string):
    """Safely unicode objects to UTF-8. If it's a binary string, just return
    it.
    """
    if isinstance(string, basestring):
        return safe_unicode(string).encode('utf-8')
    return string

