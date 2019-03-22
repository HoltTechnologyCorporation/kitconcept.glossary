# -*- coding: utf-8 -*-
from kitconcept.glossary.interfaces import IGlossarySettings
from plone import api
from plone.app.layout.viewlets import ViewletBase
from plone.i18n.normalizer.base import baseNormalize
from plone.memoize import ram
from Products.CMFPlone.utils import safe_unicode
from Products.Five.browser import BrowserView

import json
import zope.ucol


def _catalog_counter_cachekey(method, self):
    """Return a cachekey based on catalog updates."""

    catalog = api.portal.get_tool('portal_catalog')
    return str(catalog.getCounter())


class TermView(BrowserView):

    """Default view for Term type"""

    def get_entry(self):
        """Get term in the desired format"""

        item = {
            'term': self.context.title,
            'variants': self.context.variants,
            'definition': self.context.definition.raw,
        }
        return item


class GlossaryView(BrowserView):

    """Default view of Glossary type"""

    @ram.cache(_catalog_counter_cachekey)
    def get_entries(self):
        """Get glossary entries and keep them in the desired format"""

        catalog = api.portal.get_tool('portal_catalog')
        path = '/'.join(self.context.getPhysicalPath())
        query = dict(portal_type='Term', path={'query': path, 'depth': 1})

        items = {}
        for brain in catalog(**query):
            index = baseNormalize(brain.Title)[0].upper()
            if index not in items:
                items[index] = []
            item = {
                'term': brain.Title,
                'definition': brain.definition,
            }
            items[index].append(item)
            if brain.variants is None:
                continue
            for variant in brain.variants:
                index = baseNormalize(variant)[0].upper()
                item = {
                    'term': variant,
                    'definition': brain.definition,
                }
                items[index].append(item)

        language = api.portal.get_current_language()
        collator = zope.ucol.Collator(str(language))

        for k in items:
            items[k] = sorted(items[k], key=lambda term: collator.key(safe_unicode(term['term'])))

        return items

    def letters(self):
        """Return all letters sorted"""
        return sorted(self.get_entries())

    def terms(self, letter):
        """Return all terms of one letter"""
        return self.get_entries()[letter]


class GlossaryStateView(BrowserView):
    """Glossary State view used to enable or disable resources

    This is called by JS and CSS resources registry
    """

    @property
    def tooltip_is_enabled(self):
        """Check if term tooltip is enabled."""
        return api.portal.get_registry_record(
            IGlossarySettings.__identifier__ + '.enable_tooltip')

    @property
    def content_type_is_enabled(self):
        """Check if we must show the tooltip in this context."""
        context = self.context
        if getattr(context, 'default_page', False) and context.id != context.default_page:
            context = context.get(context.default_page)
        portal_type = getattr(context, 'portal_type', None)
        enabled_content_types = api.portal.get_registry_record(
            IGlossarySettings.__identifier__ + '.enabled_content_types')
        return portal_type in enabled_content_types

    def __call__(self):
        response = self.request.response
        response.setHeader('content-type', 'application/json')

        data = {
            'enabled': self.tooltip_is_enabled and self.content_type_is_enabled,
        }
        return response.setBody(json.dumps(data))


class JsonView(BrowserView):
    """Json view that return all glossary items in json format

    This view is used into an ajax call for
    """

    @ram.cache(_catalog_counter_cachekey)
    def get_json_entries(self):
        """Get all itens and prepare in the desired format.
        Note: do not name it get_entries, otherwise caching is broken. """

        catalog = api.portal.get_tool('portal_catalog')

        items = []
        for brain in catalog(portal_type='Term'):
            items.append({
                'term': brain.Title,
                'definition': brain.definition,
            })
            if brain.variants is None:
                continue
            for variant in brain.variants:
                items.append({
                    'term': variant,
                    'definition': brain.definition,
                })

        return items

    def __call__(self):
        response = self.request.response
        response.setHeader('content-type', 'application/json')

        return response.setBody(json.dumps(self.get_json_entries()))


class ResourcesViewlet(ViewletBase):
    """This viewlet inserts static resources on page header."""
