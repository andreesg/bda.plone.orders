# -*- coding: utf-8 -*-
from bda.plone.orders import interfaces as ifaces
from bda.plone.orders.interfaces import IDynamicMailTemplateLibrary
from bda.plone.orders.interfaces import IDynamicMailTemplateLibraryStorage
from BTrees.OOBTree import OOBTree
from zope.annotation import IAnnotations
from zope.component import queryAdapter
from zope.interface import implementer


###############################################################################
# en
###############################################################################

ORDER_TICKET_SUBJECT_EN = u"Teylers Museum E-tickets"
ORDER_TICKET_SUBJECT_NL = u"Teylers Museum E-tickets"

ORDER_SUBJECT_EN = u'Order %s received.'

RESERVATION_SUBJECT_EN = u'Reservation %s received.'

ORDER_TICKET_EN = """\
<html>
    <head></head>
    <body>
        <p><strong>Please do not forget to print your E-Tickets:</strong><br>
        <a href="%(download_link)s">Download your tickets</a></p>

        <p>Dear %(top_salutation)s,<br>
        We have received your order and confirm the following reservation:</p>
        
        <p><strong>Tickets:</strong><br>
        %(item_listing)s<br>
        <strong>Total price:</strong> € %(total_price)s
        </p>

        <p>Please print this email. This is your order confirmation.<br>Click on the following link to print your e-tickets: <a href="%(download_link)s">Download your tickets</a></p>
        
        <p>Your order is registered as follows:<br>
        Order number: <strong>%(ordernumber)s</strong><br>
        Name: <strong>%(name_salutation)s %(personal_data.firstname)s %(personal_data.lastname)s</strong><br></p>

        <p>If you have any questions regarding your reservation, please contact the Teylers Museum info@teylersmuseum.nl</p>

        <p>We wish you a great visit!</p>

        <p>Kind regards,<br>
        Teylers Museum</p>
    </body>
</html>
"""

ORDER_TICKET_NL = """\
<html>
    <head></head>
    <body>
        <p><strong>Vergeet niet uw E-Ticket(s) en deze E-mail te printen:</strong><br>
        <a href="%(download_link)s">Download E-tickets</a></p>

        <p>Geachte %(top_salutation)s,<br>
        Wij hebben uw bestelling ontvangen en bevestigen hierbij de volgende boeking:</p>
        
        <p><strong>Tickets:</strong><br>
        %(item_listing)s<br>
        <strong>Totaalprijs:</strong> € %(total_price)s</p>

        <p>Print deze e-mail. Dit is uw boekingsbevestiging.<br>Uw e-tickets kunt u printen via onderstaande link: <a href="%(download_link)s">Download E-tickets</a></p>
        
        <p>Uw boeking is als volgt geregistreerd:<br>
        Order number: <strong>%(ordernumber)s</strong><br>
        Naam: <strong>%(name_salutation)s %(personal_data.firstname)s %(personal_data.lastname)s</strong><br></p>

        <p>Indien u vragen heeft over uw boeking, kunt u contact opnemen met het Teylers Museum via <a href="mailto:info@teylersmuseum.nl">info@teylersmuseum.nl</a></p>

        <p>Wij wensen u een plezierig bezoek!</p>

        <p>Hartelijke groeten,<br>
        Teylers Museum</p>
    </body>
</html>
"""

ORDER_TICKET_EN = """\
<html>
    <head></head>
    <body>
        <p>Thank you very much for your order. We look forward welcoming you. Please find your tickets attached in this e-mail.</p>

        <p>For questions on your order you can contact info@teylersmuseum.nl.</p>

        <p>The website of the Teylers Museum contains an immense amount of background and topical information. If you would like to prepare your visit in advance, have a look at <a href="http://www.teylersmuseum.nl">www.teylersmuseum.nl</a> or join us on social media.</p>
    </body>
</html>
"""

ORDER_TICKET_NL = """\
<html>
    <head></head>
    <body>
        <p>Hartelijk bedankt voor uw bestelling. Uw tickets zijn bijgevoegd in de bijlage. Wij kijken zeer uit naar uw komst.</p>

        <p>Heeft u vragen over uw bestelling, neem dan contact opnemen met info@teylersmuseum.nl.</p>

        <p>De website van het Teylers Museum bevat veel achtergrond- en actuele informatie. Mocht u alvast uw bezoek willen voorbereiden gaat u dan naar <a href="http://www.teylersmuseum.nl">www.teylersmuseum.nl</a> of volg ons op sociale media.</p>
    </body>
</html>
"""

ORDER_BODY_EN = """
Date: %(date)s

Thank you for your order:

Ordernumber: %(ordernumber)s

Personal Data:
Name: %(personal_data.firstname)s %(personal_data.lastname)s
Phone: %(personal_data.phone)s
Email: %(personal_data.email)s

Address:
Street: %(billing_address.street)s
ZIP: %(billing_address.zip)s
City: %(billing_address.city)s
Country: %(billing_address.country)s
%(delivery_address)s
Comment:
%(order_comment.comment)s

Ordered items:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

ORDER_BODY_NL = """

Datum: %(date)s

Bedankt voor uw bestelling:

Bestelnummer: %(ordernumber)s

Persoonsgegevens:
Naam: %(personal_data.lastname)s
Telefoonnummer:  %(personal_data.phone)s
Email: %(personal_data.email)s

Adres:
Straat: %(billing_address.street)s
Postcode: %(billing_address.zip)s
Stad: %(billing_address.city)s
Land: %(billing_address.country)s
%(delivery_address)s
Opmerkingen:
%(order_comment.comment)s

Bestelde producten:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

RESERVATION_BODY_EN = """
Date: %(date)s

Thank you for your reservation:

Ordernumber: %(ordernumber)s
Reservation details: %(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Personal Data:
Name: %(personal_data.firstname)s %(personal_data.lastname)s
Company: %(personal_data.company)s
Phone: %(personal_data.phone)s
Email: %(personal_data.email)s

Address:
Street: %(billing_address.street)s
ZIP: %(billing_address.zip)s
City: %(billing_address.city)s
Country: %(billing_address.country)s
%(delivery_address)s
Comment:
%(order_comment.comment)s

Ordered items:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

DELIVERY_ADDRESS_EN = """
Delivery Address:
Name: %(delivery_address.firstname)s %(delivery_address.lastname)s
Company: %(delivery_address.company)s
Street: %(delivery_address.street)s
ZIP: %(delivery_address.zip)s
City: %(delivery_address.city)s
Country: %(delivery_address.country)s
"""


###############################################################################
# de
###############################################################################

ORDER_SUBJECT_DE = u'Bestellung %s erhalten.'

RESERVATION_SUBJECT_DE = u'Reservierung %s erhalten.'

ORDER_BODY_DE = """
Datum: %(date)s

Besten Dank für Ihre Bestellung:

Bestellnummer: %(ordernumber)s
Details zur Bestellung: %(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Persönliche Angaben:
Name: %(personal_data.firstname)s %(personal_data.lastname)s
Firma: %(personal_data.company)s
Telefon: %(personal_data.phone)s
E-Mail: %(personal_data.email)s

Adresse:
Strasse: %(billing_address.street)s
Postleitzahl: %(billing_address.zip)s
Ort: %(billing_address.city)s
Land: %(billing_address.country)s
%(delivery_address)s
Kommentar:
%(order_comment.comment)s

Bestellte Artikel:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

RESERVATION_BODY_DE = """
Datum: %(date)s

Besten Dank für Ihre Reservierung:

Bestellnummer: %(ordernumber)s
Details zur Reservierung: %(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Persönliche Angaben:
Name: %(personal_data.firstname)s %(personal_data.lastname)s
Firma: %(personal_data.company)s
Telefon: %(personal_data.phone)s
E-Mail: %(personal_data.email)s

Adresse:
Strasse: %(billing_address.street)s
Postleitzahl: %(billing_address.zip)s
Ort: %(billing_address.city)s
Land: %(billing_address.country)s
%(delivery_address)s
Kommentar:
%(order_comment.comment)s

Bestellte Artikel:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""  # noqa

DELIVERY_ADDRESS_DE = """
Lieferadresse:
Name: %(delivery_address.firstname)s %(delivery_address.lastname)s
Firma: %(delivery_address.company)s
Strasse: %(delivery_address.street)s
Postleitzahl: %(delivery_address.zip)s
Ort: %(delivery_address.city)s
Land: %(delivery_address.country)s
"""


###############################################################################
# fr
###############################################################################

ORDER_SUBJECT_FR = u'votre commande %s.'

RESERVATION_SUBJECT_FR = u'votre réservation %s.'

ORDER_BODY_FR = """
Date: %(date)s

Nous vous remercions pour votre commande:

No. de commande: %(ordernumber)s
%(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Données personnelles:
Nom: %(personal_data.firstname)s %(personal_data.lastname)s
Entreprise: %(personal_data.company)s
Téléphone: %(personal_data.phone)s
E-Mail: %(personal_data.email)s

Adresse:
Rue: %(billing_address.street)s
No. Postal: %(billing_address.zip)s
Localité: %(billing_address.city)s
Pays: %(billing_address.country)s
%(delivery_address)s
Commentaires:
%(order_comment.comment)s

Produit commandé:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

RESERVATION_BODY_FR = """
Date: %(date)s

Nous vous remercions pour votre réservation:

No. de commande: %(ordernumber)s
%(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Données personnelles:
Nom: %(personal_data.firstname)s %(personal_data.lastname)s
Entreprise: %(personal_data.company)s
Téléphone: %(personal_data.phone)s
E-Mail: %(personal_data.email)s

Adresse:
Rue: %(billing_address.street)s
No. Postal: %(billing_address.zip)s
Localité: %(billing_address.city)s
Pays: %(billing_address.country)s
%(delivery_address)s
Commentaires:
%(order_comment.comment)s

Produit commandé:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

DELIVERY_ADDRESS_FR = """
Adresse de livraison:
Nom: %(delivery_address.firstname)s %(delivery_address.lastname)s
Entreprise: %(delivery_address.company)s
Rue: %(delivery_address.street)s
No. Postal: %(delivery_address.zip)s
Localité: %(delivery_address.city)s
Pays: %(delivery_address.country)s
"""


###############################################################################
# it
###############################################################################

ORDER_SUBJECT_IT = u'Il tuo ordine %s.'

RESERVATION_SUBJECT_IT = u'Il tuo prenotazione %s.'

ORDER_BODY_IT = """
Data: %(date)s

Grazie per l'ordine effettuato:

Numero d'ordine: %(ordernumber)s
%(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Dati personali:
Nome: %(personal_data.firstname)s %(personal_data.lastname)s
Ditta: %(personal_data.company)s
Telefono: %(personal_data.phone)s

Indirizzo:
Via: %(billing_address.street)s
CAP: %(billing_address.zip)s
Città: %(billing_address.city)s
Nazione: %(billing_address.country)s
%(delivery_address)s
Commento:
%(order_comment.comment)s

Articolo ordinato:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

RESERVATION_BODY_IT = """
Data: %(date)s

Grazie per l'prenotazione effettuato:

Numero d'ordine: %(ordernumber)s
%(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Dati personali:
Nome: %(personal_data.firstname)s %(personal_data.lastname)s
Ditta: %(personal_data.company)s
Telefono: %(personal_data.phone)s

Indirizzo:
Via: %(billing_address.street)s
CAP: %(billing_address.zip)s
Città: %(billing_address.city)s
Nazione: %(billing_address.country)s
%(delivery_address)s
Commento:
%(order_comment.comment)s

Articolo ordinato:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

DELIVERY_ADDRESS_IT = """
Indirizzo di spedizione:
Nome: %(delivery_address.firstname)s %(delivery_address.lastname)s
Ditta: %(delivery_address.company)s
Via: %(delivery_address.street)s
CAP: %(delivery_address.zip)s
Città: %(delivery_address.city)s
Nazione: %(delivery_address.country)s
"""

###############################################################################
# no
###############################################################################

ORDER_SUBJECT_NO = u'Bestilling %s mottatt.'

RESERVATION_SUBJECT_NO = u'Bestilling %s mottatt.'

ORDER_BODY_NO = """
Dato: %(date)s

Takk for din bestilling:

Ordernummer: %(ordernumber)s
%(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Personlig info:
Navn: %(personal_data.firstname)s %(personal_data.lastname)s
Firma: %(personal_data.company)s
Telefon: %(personal_data.phone)s
Epost: %(personal_data.email)s

Adr:
Gate/Vei: %(billing_address.street)s
Postnr.: %(billing_address.zip)s
Poststed: %(billing_address.city)s
Land: %(billing_address.country)s
%(delivery_address)s
Kommentar:
%(order_comment.comment)s

Bestilte produkter:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

RESERVATION_BODY_NO = """
Dato: %(date)s

Takk for din bestilling:

Ordernummer: %(ordernumber)s
%(portal_url)s/@@showorder?ordernumber=%(ordernumber)s

Personlig info:
Navn: %(personal_data.firstname)s %(personal_data.lastname)s
Firma: %(personal_data.company)s
Telefon: %(personal_data.phone)s
Epost: %(personal_data.email)s

Adr:
Gate/Vei: %(billing_address.street)s
Postnr.: %(billing_address.zip)s
Poststed: %(billing_address.city)s
Land: %(billing_address.country)s
%(delivery_address)s
Kommentar:
%(order_comment.comment)s

Bestilte produkter:
%(item_listing)s

%(order_summery)s%(global_text)s%(payment_text)s
"""

DELIVERY_ADDRESS_NO = """
Leveringsadr.:
Navn: %(delivery_address.firstname)s %(delivery_address.lastname)s
Firma: %(delivery_address.company)s
gate/Vei: %(delivery_address.street)s
Postnr.: %(delivery_address.zip)s
Poststed: %(delivery_address.city)s
Land: %(delivery_address.country)s
"""


###############################################################################
# language templates
###############################################################################

ORDER_TEMPLATES = {
    'nl': {
        'ticket_subject': ORDER_TICKET_SUBJECT_NL,
        'subject': ORDER_SUBJECT_EN,
        'body': ORDER_BODY_NL,
        'ticket': ORDER_TICKET_NL,
        'delivery_address': DELIVERY_ADDRESS_EN},
    'en': {
        'ticket_subject': ORDER_TICKET_SUBJECT_EN,
        'subject': ORDER_SUBJECT_EN,
        'body': ORDER_BODY_EN,
        'ticket': ORDER_TICKET_EN,
        'delivery_address': DELIVERY_ADDRESS_EN},
    'de': {
        'subject': ORDER_SUBJECT_DE,
        'body': ORDER_BODY_DE,
        'delivery_address': DELIVERY_ADDRESS_DE},
    'fr': {
        'subject': ORDER_SUBJECT_FR,
        'body': ORDER_BODY_FR,
        'delivery_address': DELIVERY_ADDRESS_FR},
    'it': {
        'subject': ORDER_SUBJECT_IT,
        'body': ORDER_BODY_IT,
        'delivery_address': DELIVERY_ADDRESS_IT},
    'no': {
        'subject': ORDER_SUBJECT_NO,
        'body': ORDER_BODY_NO,
        'delivery_address': DELIVERY_ADDRESS_NO}
}

RESERVATION_TEMPLATES = {
    'en': {
        'subject': RESERVATION_SUBJECT_EN,
        'body': RESERVATION_BODY_EN,
        'ticket': ORDER_TICKET_EN,
        'delivery_address': DELIVERY_ADDRESS_EN},
    'de': {
        'subject': RESERVATION_SUBJECT_DE,
        'body': RESERVATION_BODY_DE,
        'delivery_address': DELIVERY_ADDRESS_DE},
    'fr': {
        'subject': RESERVATION_SUBJECT_FR,
        'body': RESERVATION_BODY_FR,
        'delivery_address': DELIVERY_ADDRESS_FR},
    'it': {
        'subject': RESERVATION_SUBJECT_IT,
        'body': RESERVATION_BODY_IT,
        'delivery_address': DELIVERY_ADDRESS_IT},
    'no': {
        'subject': RESERVATION_SUBJECT_NO,
        'body': RESERVATION_BODY_NO,
        'delivery_address': DELIVERY_ADDRESS_NO}
}


def get_order_templates(context):
    lang = context.restrictedTraverse('@@plone_portal_state').language()
    return ORDER_TEMPLATES.get(lang, ORDER_TEMPLATES['en'])


def get_reservation_templates(context):
    lang = context.restrictedTraverse('@@plone_portal_state').language()
    return RESERVATION_TEMPLATES.get(lang, RESERVATION_TEMPLATES['en'])


# list of template attributes which are required. by default, no attributes are
# required.
REQUIRED_TEMPLATE_ATTRS = list()


# dictionary with attributes valid in mail template as keys, values are used
# for template validation
DEFAULT_TEMPLATE_ATTRS = {
    'created': '14.2.2014 14:42',
    'ordernumber': '123456',
    'salaried': ifaces.SALARIED_NO,
    'state': ifaces.STATE_NEW,
    'personal_data.company': 'ACME LTD.',
    'personal_data.email': 'max.mustermann@example.com',
    'personal_data.gender': 'male',
    'personal_data.firstname': 'Max',
    'personal_data.phone': '+43 123 456 78 90',
    'personal_data.lastname': 'Mustermann',
    'billing_address.city': 'Springfield',
    'billing_address.country': 'Austria',
    'billing_address.street': 'Musterstrasse',
    'billing_address.zip': '1234',
    'order_comment.comment': 'Comment',
    'payment_selection.payment': 'six_payment',
}


class DynamicMailTemplate(object):
    """Dynamic Mail Template based on str.format
    """

    def __init__(self, required=[], defaults={}):
        """Initialize a new template

        required
            a list of keys which are required in the data to be rendered.
            all other values are taken from defaults if not provided.

        defaults
            a complete set of values for the template. used for validation,
            so it has to include all required as well.
        """
        for key in required:
            if key in defaults:
                continue
            raise ValueError(
                'All required must be in defaults too, missing: '
                '{0}'.format(key)
            )
        self.required = required
        self.defaults = defaults

    def normalized(self, keys=[], indict={}):
        if keys and indict:
            raise ValueError('Only one kwargs please.')
        if keys:
            result = []
            for key in keys:
                result.append(key.replace('.', '_'))
            return result
        if indict:
            result = {}
            for key, value in indict.items():
                if isinstance(value, str):
                    value = value.decode('utf-8')
                result[key.replace('.', '_')] = value
            return result
        raise ValueError('Only one kwargs please.')

    def validate(self, template):
        """validates if the template can be rendered.

        uses default values to achieve this

        template
            a unicode string meant to be rendered using python string format
            method
        """
        assert isinstance(template, unicode), 'template must be unicode'
        try:
            self(template, self.defaults)
        except KeyError, e:
            return False, u'Variable "{0}" is not available.'.format(e.message)
        except Exception, e:
            return False, e.message
        return True, ''

    def __call__(self, template, data):
        """render template with data
        """
        assert isinstance(template, unicode), 'template must be unicode'
        for key in self.required:
            if key not in data:
                raise KeyError('Required key {0} is missing.'.format(key))
        return template.format(**self.normalized(indict=data))


DYNAMIC_MAIL_LIBRARY_KEY = "bda.plone.order.dynamic_mail_lib"


@implementer(IDynamicMailTemplateLibrary)
class DynamicMailTemplateLibraryAquierer(object):

    def __init__(self, context):
        self.context = context

    def _parent(self):
        if not hasattr(self.context, '__parent__'):
            return None
        if self.context.__parent__:
            dmt_lib = queryAdapter(
                self.context.__parent__,
                IDynamicMailTemplateLibrary,
            )
            return dmt_lib

    def keys(self):
        parent = self._parent()
        if parent is None:
            return []
        return parent.keys()

    def __getitem__(self, name):
        parent = self._parent()
        if parent is not None:
            return parent[name]
        raise KeyError('Can not aquire key %s' % name)

    def __setitem__(self, name, template):
        raise NotImplementedError(
            'acquierer do not set on parent (permissions)'
        )

    def __delitem__(self, name):
        raise NotImplementedError(
            'acquierer do not delete on parent (permissions)'
        )


@implementer(IDynamicMailTemplateLibraryStorage)
class DynamicMailTemplateLibraryStorage(DynamicMailTemplateLibraryAquierer):

    @property
    def _storage(self):
        annotations = IAnnotations(self.context)
        if DYNAMIC_MAIL_LIBRARY_KEY not in annotations:
            annotations[DYNAMIC_MAIL_LIBRARY_KEY] = OOBTree()
        return annotations[DYNAMIC_MAIL_LIBRARY_KEY]

    def direct_keys(self):
        return [_ for _ in self._storage.keys()]

    def keys(self):
        result = self.direct_keys()
        parent_keys = super(DynamicMailTemplateLibraryStorage, self).keys()
        for key in parent_keys:
            if key not in result:  # child wins
                result.append(key)
        return result

    def __getitem__(self, name):
        try:
            return self._storage[name]
        except KeyError:
            return super(
                DynamicMailTemplateLibraryStorage,
                self
            ).__getitem__(name)

    def __setitem__(self, name, template):
        self._storage[name] = template

    def __delitem__(self, name):
        del self._storage[name]
