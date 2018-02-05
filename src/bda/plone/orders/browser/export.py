# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from Acquisition import aq_parent
from Products.CMFPlone.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from StringIO import StringIO
from bda.plone.cart import get_item_stock
from bda.plone.cart import get_object_by_uid
from bda.plone.orders import message_factory as _
from bda.plone.orders import permissions
from bda.plone.orders import safe_encode
from bda.plone.orders import safe_filename
from bda.plone.orders.browser.views import OrdersContentView
from bda.plone.orders.browser.views import customers_form_vocab
from bda.plone.orders.browser.views import vendors_form_vocab
from bda.plone.orders.common import DT_FORMAT
from bda.plone.orders.common import OrderData
from bda.plone.orders.common import get_bookings_soup
from bda.plone.orders.common import get_order
from bda.plone.orders.common import get_orders_soup
from bda.plone.orders.common import get_vendor_uids_for
from bda.plone.orders.common import get_vendors_for
from bda.plone.orders.interfaces import IBuyable
from decimal import Decimal
from odict import odict
from plone.uuid.interfaces import IUUID
from repoze.catalog.query import Any
from repoze.catalog.query import Eq
from repoze.catalog.query import Ge
from repoze.catalog.query import Le
from yafowil.base import ExtractionError
from yafowil.controller import Controller
from yafowil.plone.form import YAMLForm
import csv
import datetime
import plone.api
import uuid
import yafowil.loader  # noqa
from bda.plone.orders import vocabularies as vocabs
from zope.i18n import translate
from bda.plone.orders.browser.views import get_tours_events
import json
from souper.soup import get_soup
from bda.plone.orders.interfaces import INotificationSettings


from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.utils import formataddr
import smtplib
import datetime
from Products.CMFPlone.interfaces import IPloneSiteRoot

from bda.plone.cart import ascur

class DialectExcelWithColons(csv.excel):
    delimiter = ';'


csv.register_dialect('excel-colon', DialectExcelWithColons)


ORDER_EXPORT_ATTRS = [
    'uid',
    'created',
    'ordernumber',
    'cart_discount_net',
    'cart_discount_vat',
    'personal_data.company',
    'personal_data.email',
    'personal_data.gender',
    'personal_data.firstname',
    'personal_data.phone',
    'personal_data.lastname',
    'billing_address.city',
    'billing_address.country',
    'billing_address.street',
    'billing_address.zip',
    'delivery_address.alternative_delivery',
    'delivery_address.city',
    'delivery_address.company',
    'delivery_address.country',
    'delivery_address.firstname',
    'delivery_address.street',
    'delivery_address.lastname',
    'delivery_address.zip',
    'order_comment.comment',
    'payment_selection.payment',
]

ORDER_EXPORT_ATTRS_EXTENDED = [
    'created',
    'ordernumber',
    'payment_selection.payment',
]

ORDER_HEADERS = [
    'Datum',
    'Bestelnummer',
    'Betaling',
]

COMPUTED_ORDER_EXPORT_ATTRS = odict()
BOOKING_EXPORT_ATTRS = [
    'title',
    'buyable_comment',
    'buyable_count',
    'quantity_unit',
    'net',
    'discount_net',
    'vat',
    'currency',
    'state',
    'salaried',
    'exported',
]
COMPUTED_BOOKING_EXPORT_ATTRS = odict()

BOOKING_EXPORT_ATTRS_EXTENDED = [
    'title',
    'item_number',
    'buyable_count',
    'net',
    'vat',
    'salaried'
]

BOOKING_HEADERS = [
    'Titel',
    'Artikelnummer',
    'Aantal',
    'Artikel netto',
    'BTW',
    'Betaald'
]

BOOKING_EXPORT_ATTRS_ORDERS = []

COMPUTED_BOOKING_EXPORT_ATTRS = odict()

def buyable_available(context, booking):
    obj = get_object_by_uid(context, booking.attrs['buyable_uid'])
    if not obj:
        return None
    item_stock = get_item_stock(obj)
    if not item_stock:
        return None
    return item_stock.available


def buyable_overbook(context, booking):
    obj = get_object_by_uid(context, booking.attrs['buyable_uid'])
    if not obj:
        return None
    item_stock = get_item_stock(obj)
    if not item_stock:
        return None
    return item_stock.overbook


def buyable_url(context, booking):
    obj = get_object_by_uid(context, booking.attrs['buyable_uid'])
    if not obj:
        return None
    return obj.absolute_url()

def order_total(context, order):
    return float(ascur(order.total))

def order_vat(context, order):
    return float(ascur(order.vat))

def order_bookings(context, order):
    bookings = []

    for booking in order.bookings:
        bookings.append("%s x %s" %(booking.attrs.get('buyable_count', ''), booking.attrs.get('title', '')))
    
    return " | ".join(bookings)
    

#COMPUTED_BOOKING_EXPORT_ATTRS['buyable_available'] = buyable_available
#COMPUTED_BOOKING_EXPORT_ATTRS['buyable_overbook'] = buyable_overbook
COMPUTED_BOOKING_EXPORT_ATTRS['buyable_url'] = buyable_url
COMPUTED_ORDER_EXPORT_ATTRS['vat'] = order_vat
COMPUTED_ORDER_EXPORT_ATTRS['order_total'] = order_total
COMPUTED_ORDER_EXPORT_ATTRS['items'] = order_bookings

COMPUTED_HEADERS = [
    'URL'
]

COMPUTED_ORDER_HEADERS = [
    'BTW',
    'Totaal',
    'Bestellingen'
]


def cleanup_for_csv(value):
    """Cleanup a value for CSV export.
    """
    if isinstance(value, datetime.datetime):
        value = value.strftime(DT_FORMAT)
    if value == '-':
        value = ''
    if isinstance(value, float) or \
       isinstance(value, Decimal):
        value = value
    return safe_encode(value)


class ExportOrdersForm(YAMLForm, OrdersContentView):
    browser_template = ViewPageTemplateFile('export.pt')
    form_template = 'bda.plone.orders.browser:forms/orders_export.yaml'
    message_factory = _
    action_resource = 'exportorders'

    def __call__(self):
        # check if authenticated user is vendor
        if not get_vendors_for():
            raise Unauthorized
        self.prepare()
        controller = Controller(self.form, self.request)
        if not controller.next:
            self.rendered_form = controller.rendered
            return self.browser_template(self)
        return controller.next

    def vendor_vocabulary(self):
        return vendors_form_vocab()

    def vendor_mode(self):
        return len(vendors_form_vocab()) > 2 and 'edit' or 'skip'

    def customer_vocabulary(self):
        return customers_form_vocab()

    def customer_mode(self):
        return len(customers_form_vocab()) > 2 and 'edit' or 'skip'

    def from_before_to(self, widget, data):
        from_date = data.fetch('exportorders.from').extracted
        to_date = data.fetch('exportorders.to').extracted
        if to_date <= from_date:
            raise ExtractionError(_('from_date_before_to_date',
                                    default=u'From-date after to-date'))
        return to_date

    def export(self, widget, data):
        self.vendor = self.request.form.get('exportorders.vendor')
        self.customer = self.request.form.get('exportorders.customer')
        self.from_date = data.fetch('exportorders.from').extracted
        self.to_date = data.fetch('exportorders.to').extracted

    def export_val(self, record, attr_name):
        """Get attribute from record and cleanup.
        Since the record object is available, you can return aggregated values.
        """
        val = record.attrs.get(attr_name)

        # Translate salaried val
        if attr_name in ['salaried']:
            if val == 'yes':
                val = 'Ja'
            elif val == 'no':
                val = 'Nee'
            else:
                val = val

        if attr_name in ['payment_selection.payment']:
            if val == 'mollie_payment':
                val = "iDeal"

        if attr_name in ['item_number']:
            if not val:
                uid = record.attrs.get('buyable_uid')
                obj = get_object_by_uid(self.context, uid)
                val = getattr(obj, 'item_number', '')

        return cleanup_for_csv(val)

    def _get_buyables_in_context(self):
        catalog = plone.api.portal.get_tool("portal_catalog")
        path = '/'.join(self.context.getPhysicalPath())
        brains = catalog(path=path, object_provides=IBuyable.__identifier__)
        for brain in brains:
            yield brain.UID

    def csv_context(self):
        context = self.context

        # prepare csv writer
        sio = StringIO()
        ex = csv.writer(sio, dialect='excel-colon', quoting=csv.QUOTE_MINIMAL)
        # exported column keys as first line
        ex.writerow(ORDER_HEADERS +
                    COMPUTED_ORDER_HEADERS +
                    BOOKING_HEADERS +
                    COMPUTED_HEADERS)

        bookings_soup = get_bookings_soup(context)

        # First, filter by allowed vendor areas
        vendor_uids = get_vendor_uids_for()
        query_b = Ge('created', self.from_date) & Le('created', self.to_date)
        query_b = query_b & Any('vendor_uid', vendor_uids)

        # Second, query for the buyable
        buyable_uids = self._get_buyables_in_context()
        query_b = query_b & Any('buyable_uid', buyable_uids)

        all_orders = {}
        for booking in bookings_soup.query(query_b, sort_index='created'):
            booking_attrs = list()
            # booking export attrs
            for attr_name in BOOKING_EXPORT_ATTRS_EXTENDED:
                val = self.export_val(booking, attr_name)
                booking_attrs.append(val)
            # computed booking export attrs
            for attr_name in COMPUTED_BOOKING_EXPORT_ATTRS:
                cb = COMPUTED_BOOKING_EXPORT_ATTRS[attr_name]
                val = cb(context, booking)
                val = cleanup_for_csv(val)
                booking_attrs.append(val)

            # create order_attrs, if it doesn't exist
            order_uid = booking.attrs.get('order_uid')
            if order_uid not in all_orders:
                order = get_order(context, order_uid)
                order_data = OrderData(context,
                                       order=order,
                                       vendor_uids=vendor_uids)
                order_attrs = list()
                # order export attrs
                for attr_name in ORDER_EXPORT_ATTRS_EXTENDED:
                    val = self.export_val(order, attr_name)
                    order_attrs.append(val)
                # computed order export attrs
                for attr_name in COMPUTED_ORDER_EXPORT_ATTRS:
                    cb = COMPUTED_ORDER_EXPORT_ATTRS[attr_name]
                    val = cb(self.context, order_data)
                    val = cleanup_for_csv(val)
                    order_attrs.append(val)
                all_orders[order_uid] = order_attrs

            ex.writerow(all_orders[order_uid] + booking_attrs)
        
        s_start = self.from_date.strftime('%G-%m-%d_%H-%M-%S')
        s_end = self.to_date.strftime('%G-%m-%d_%H-%M-%S')
        filename = 'tickets-export-%s-%s.csv' % (s_start, s_end)
        self.request.response.setHeader('Content-Type', 'text/csv')
        self.request.response.setHeader('Content-Disposition',
                                        'attachment; filename=%s' % filename)

        ret = sio.getvalue()
        sio.close()
        return ret

    def csv(self, request):

        #if not IPloneSiteRoot.providedBy(self.context):
        #return self.csv_context()

        # get orders soup
        orders_soup = get_orders_soup(self.context)
        # get bookings soup
        bookings_soup = get_bookings_soup(self.context)
        # fetch user vendor uids
        vendor_uids = get_vendor_uids_for()
        # base query for time range
        query = Ge('created', self.from_date) & Le('created', self.to_date)
        # filter by given vendor uid or user vendor uids
        vendor_uid = self.vendor
        if vendor_uid:
            vendor_uid = uuid.UUID(vendor_uid)
            # raise if given vendor uid not in user vendor uids
            if vendor_uid not in vendor_uids:
                raise Unauthorized
            query = query & Any('vendor_uids', [vendor_uid])
        else:
            query = query & Any('vendor_uids', vendor_uids)
        # filter by customer if given
        customer = self.customer
        if customer:
            query = query & Eq('creator', customer)
        # prepare csv writer
        sio = StringIO()
        ex = csv.writer(sio, dialect='excel-colon', quoting=csv.QUOTE_MINIMAL)
        # exported column keys as first line
        ex.writerow(ORDER_HEADERS + COMPUTED_ORDER_HEADERS)
        
        # query orders
        for order in orders_soup.query(query, sort_index='created'):
            # restrict order bookings for current vendor_uids
            order_data = OrderData(self.context,
                                   order=order,
                                   vendor_uids=vendor_uids)
            order_attrs = list()
            # order export attrs
            for attr_name in ORDER_EXPORT_ATTRS_EXTENDED:
                val = self.export_val(order, attr_name)
                order_attrs.append(val)
            
            # computed order export attrs
            for attr_name in COMPUTED_ORDER_EXPORT_ATTRS:
                cb = COMPUTED_ORDER_EXPORT_ATTRS[attr_name]
                val = cb(self.context, order_data)
                val = cleanup_for_csv(val)
                order_attrs.append(val)

            """for booking in order_data.bookings:
                booking_attrs = list()
                # booking export attrs
                for attr_name in BOOKING_EXPORT_ATTRS:
                    val = self.export_val(booking, attr_name)
                    booking_attrs.append(val)
                # computed booking export attrs
                for attr_name in COMPUTED_BOOKING_EXPORT_ATTRS:
                    cb = COMPUTED_BOOKING_EXPORT_ATTRS[attr_name]
                    val = cb(self.context, booking)
                    val = cleanup_for_csv(val)
                    booking_attrs.append(val)
                #ex.writerow(order_attrs + booking_attrs)
                booking.attrs['exported'] = True
                bookings_soup.reindex(booking)"""

            if getattr(order_data, 'salaried', None) == "yes":
                ex.writerow(order_attrs)

        # create and return response
        s_start = self.from_date.strftime('%G-%m-%d_%H-%M-%S')
        s_end = self.to_date.strftime('%G-%m-%d_%H-%M-%S')
        filename = 'tickets-export-%s-%s.csv' % (s_start, s_end)
        self.request.response.setHeader('Content-Type', 'text/csv')
        self.request.response.setHeader('Content-Disposition',
                                        'attachment; filename=%s' % filename)
        ret = sio.getvalue()
        sio.close()
        return ret


## TOURS

class ExportToursContextual(BrowserView):

    def __call__(self):
        user = plone.api.user.get_current()
        # check if authenticated user is vendor

        if not hasattr(user, 'checkPermission'):
            raise Unauthorized
        if not user:
            raise Unauthorized
        if not user.checkPermission(permissions.ModifyOrders, self.context):
            raise Unauthorized

        # Special case for constructed objects like IEventOccurrence from
        # plone.app.event
        title = 'Tours' or aq_parent(self.context).title

        filename = u'{0}_{1}.csv'.format(
            safe_unicode(title),
            safe_unicode(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M'))
        )
        filename = safe_filename(filename)
        resp = self.request.response
        resp.setHeader('content-type', 'text/csv; charset=utf-8')
        resp.setHeader(
            'content-disposition',
            'attachment;filename={}'.format(filename)
        )
        return self.get_csv()

    def export_val(self, record, attr_name):
        """Get attribute from record and cleanup.
        Since the record object is available, you can return aggregated values.
        """
        val = record.attrs.get(attr_name)
        return cleanup_for_csv(val)

    def get_data_from_request(self, data_request):
        try:
            data = json.loads(data_request)
            return data
        except:
            return []

        return []

    def get_csv(self):

        datefilter = self.request.get('datefilter', None)
        statefilter = self.request.get('state', None)

        TOUR_EXPORT_ATTRS = [
            ('date', 'Datum'),
            ('quantity', 'Aantal'),
            ('last-name', 'Achternaam'),
            ('first-name', 'Voornaam'),
            ('email', 'Email'),
            ('state', 'Status')
        ]

        context = self.context

        # prepare csv writer
        sio = StringIO()
        ex = csv.writer(sio, dialect='excel-colon', quoting=csv.QUOTE_MINIMAL)
        # exported column keys as first line
        ex.writerow([attr[1] for attr in TOUR_EXPORT_ATTRS])

        data_request = self.request.get('exporttoursdata', None)

        bookings = []
        
        # Get data
        data = self.get_data_from_request(data_request)
        for elem in data:
            new_booking = {
                'date': elem['date'],
                'quantity': elem['quantity'],
                'last-name': elem['lastname'],
                'first-name': elem['firstname'],
                'email': elem['email'],
                'state': elem['status']
            }

            bookings.append(new_booking)

        for booking in bookings:
            row = [cleanup_for_csv(booking.get(attr[0], '')) for attr in TOUR_EXPORT_ATTRS]
            ex.writerow(row)

        ret = sio.getvalue()
        sio.close()

        return ret


class SendToursDataContextual(BrowserView):

    def __call__(self):
        user = plone.api.user.get_current()
        # check if authenticated user is vendor

        if not hasattr(user, 'checkPermission'):
            raise Unauthorized
        if not user:
            raise Unauthorized
        if not user.checkPermission(permissions.ModifyOrders, self.context):
            raise Unauthorized
            
        self.settings = INotificationSettings(self.context)

        tickets_folder = plone.api.content.get(path='/nl/tickets')
        data = tickets_folder.unrestrictedTraverse("@@exportorderstoursdata")
        length, res = data.query(None, booking_state="new")
        self.export_data_request = data.get_aaData(res)

        # Special case for constructed objects like IEventOccurrence from
        # plone.app.event
        title = 'Tours' or aq_parent(self.context).title

        filename = u'{0}_{1}.csv'.format(
            safe_unicode(title),
            safe_unicode(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M'))
        )
        filename = safe_filename(filename)
        resp = self.request.response
        resp.setHeader('content-type', 'text/csv; charset=utf-8')
        resp.setHeader(
            'content-disposition',
            'attachment;filename={}'.format(filename)
        )
        return self.get_csv()

    def export_val(self, record, attr_name):
        """Get attribute from record and cleanup.
        Since the record object is available, you can return aggregated values.
        """
        val = record.attrs.get(attr_name)
        return cleanup_for_csv(val)

    def transform_data(self, data):
        if data:
            result = []
            raw_data = data
            for elem in raw_data:
                result.append({
                    "date": elem[1],
                    "quantity": elem[2],
                    "lastname": elem[3],
                    "firstname": elem[4],
                    "email": elem[5],
                    "status": "Nieuw" if "Nieuw" in elem[6] else "Gecanceld"
                })

            return result

        return []

    def get_data_from_request(self, data_request):
        try:
            data_request = self.transform_data(self.export_data_request)
            return data_request
        except:
            return []

        return []

    def send_email(self, ret):

        shop_manager_address = self.settings.admin_email
        receivers = self.settings.notification_emails

        shop_manager_name = self.settings.admin_name
        if shop_manager_name:
            from_name = shop_manager_name
            mailfrom = formataddr((from_name, shop_manager_address))
        else:
            mailfrom = shop_manager_address

        todays_date = datetime.datetime.today().strftime("%Y-%m-%d")
        text = MIMEMultipart('alternative')
        msg = MIMEMultipart('mixed')
        msg['Subject'] = "%s - Lorentz Lab bookings" %(todays_date)
        msg['From'] = mailfrom
        
        attachment = MIMEApplication(ret, _subtype = "csv")
        attachment.add_header('content-disposition', 'attachment', filename='%s_bookings.csv' %(todays_date))

        message = "<h2>%s - Lorentz Lab bookings</h2><p>Please find the bookings for the date %s in the spreadsheet attached</p>" %(todays_date, todays_date)
        text.attach(MIMEText(message, 'html', 'utf-8'))
        msg.attach(text)
        msg.attach(attachment)

        for receiver in receivers.split(','):
            s = smtplib.SMTP('127.0.0.1')
            s.sendmail(mailfrom, receiver, msg.as_string())
            s.quit()

        return True

    def search_timeslot_id(self, search_id, timeslots):
        for i in range(len(timeslots)):
            if timeslots[i]['_id'] == search_id:
                return True
        return False

    def change_timeslot_quantity(self, search_id, quantity, timeslots):
        for i in range(len(timeslots)):
            if timeslots[i]['_id'] == search_id:
                timeslots[i]['quantity'] += int(quantity)
                return True
        return False

    def find_if_skipped(self, week_slot, used_timeslots):

        for used_timeslot in used_timeslots:
            timeslot = used_timeslot['_id']
            if week_slot in timeslot:
                return False

        return True

    def get_csv(self):

        datefilter = self.request.get('datefilter', None)
        statefilter = self.request.get('state', None)

        TOUR_EXPORT_ATTRS = [
            ('date', 'Datum'),
            ('quantity', 'Aantal'),
            ('last-name', 'Achternaam'),
            ('first-name', 'Voornaam'),
            ('email', 'Email'),
            ('state', 'Status')
        ]

        context = self.context

        # prepare csv writer
        sio = StringIO()
        ex = csv.writer(sio, dialect='excel-colon', quoting=csv.QUOTE_MINIMAL)
        # exported column keys as first line
        ex.writerow([attr[1] for attr in TOUR_EXPORT_ATTRS])

        data_request = self.request.get('data', None)

        bookings = []
        used_timeslots = []
        
        # Get data
        data = self.get_data_from_request(data_request)
        for elem in data:
            new_booking = {
                'date': elem['date'],
                'quantity': elem['quantity'],
                'last-name': elem['lastname'],
                'first-name': elem['firstname'],
                'email': elem['email'],
                'state': elem['status']
            }

            bookings.append(new_booking)

        TOTAL_AVAILABLE = 20

        week_slots = ['12:30 - 13:20', '14:00 - 14:50', '15:30 - 16:20']
        weekend_slots = ['11:30 - 12:20', '12:45 - 13:35', '14:30 - 15:20', '15:45 - 16:35']
        timeslots_available = week_slots
        
        if datetime.datetime.today().weekday() in [5, 6]:
             timeslots_available = weekend_slots

        for booking in bookings:
            row = [cleanup_for_csv(booking.get(attr[0], '')) for attr in TOUR_EXPORT_ATTRS]
            if booking.get('date', ''):
                if not self.search_timeslot_id(booking.get('date', ''), used_timeslots):
                    if len(used_timeslots) > 0:
                        if booking.get('date', '') != used_timeslots[-1]['_id']:
                            """ Write new row """
                            reservations_timeslot_row = ['Gereserveerd', used_timeslots[-1]['quantity'], '', '', '', '']
                            over_available = TOTAL_AVAILABLE - used_timeslots[-1]['quantity']
                            if over_available < 0:
                                over_available = 0
                            over_timeslot_row = ['Over', over_available, '', '', '', '']
                            ex.writerow(reservations_timeslot_row)
                            ex.writerow(over_timeslot_row)
                            ex.writerow(['', '', '', '', '', ''])

                    used_timeslots.append({'_id': booking.get('date', ''), 'quantity': int(booking.get('quantity', ''))})
                else:
                    self.change_timeslot_quantity(booking.get('date', ''), booking.get('quantity', ''), used_timeslots)
            ex.writerow(row)

        slot_date = None
        """ Write last row with details """
        if used_timeslots:
            reservations_timeslot_row = ['Gereserveerd', used_timeslots[-1]['quantity'], '', '', '', '']
            over_available = TOTAL_AVAILABLE - used_timeslots[-1]['quantity']
            if over_available < 0:
                over_available = 0
            over_timeslot_row = ['Over', over_available, '', '', '', '']
            ex.writerow(reservations_timeslot_row)
            ex.writerow(over_timeslot_row)
            slot_date = used_timeslots[0]['_id'].split(",")[0]
            ex.writerow(['', '', '', '', '', ''])

        for week_slot in timeslots_available:
            skipped = self.find_if_skipped(week_slot, used_timeslots)
            if skipped:
                if slot_date:
                    skipped_date = "%s, %s" %(slot_date, week_slot)
                else:
                    skipped_date = "%s" %(week_slot)

                skipped_date_row = [skipped_date, '', '', '', '', '']
                reservations_timeslot_row = ['Gereserveerd', 0, '', '', '', '']
                over_timeslot_row = ['Over', TOTAL_AVAILABLE, '', '', '', '']
                ex.writerow(skipped_date_row)
                ex.writerow(reservations_timeslot_row)
                ex.writerow(over_timeslot_row)
                ex.writerow(['', '', '', '', '', ''])


        ret = sio.getvalue()
        sio.close()

        self.send_email(ret)

        return ret




class ExportOrdersContextual(BrowserView):

    def __call__(self):
        user = plone.api.user.get_current()
        # check if authenticated user is vendor
        if not user.checkPermission(permissions.ModifyOrders, self.context):
            raise Unauthorized

        # Special case for constructed objects like IEventOccurrence from
        # plone.app.event
        title = self.context.title or aq_parent(self.context).title

        filename = u'{0}_{1}.csv'.format(
            safe_unicode(title),
            safe_unicode(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M'))
        )
        filename = safe_filename(filename)
        resp = self.request.response
        resp.setHeader('content-type', 'text/csv; charset=utf-8')
        resp.setHeader(
            'content-disposition',
            'attachment;filename={}'.format(filename)
        )
        return self.get_csv()

    def export_val(self, record, attr_name):
        """Get attribute from record and cleanup.
        Since the record object is available, you can return aggregated values.
        """
        val = record.attrs.get(attr_name)
        return cleanup_for_csv(val)

    def get_csv(self):
        context = self.context

        # prepare csv writer
        sio = StringIO()
        ex = csv.writer(sio, dialect='excel-colon', quoting=csv.QUOTE_MINIMAL)
        # exported column keys as first line
        ex.writerow(ORDER_EXPORT_ATTRS +
                    COMPUTED_ORDER_EXPORT_ATTRS.keys() +
                    BOOKING_EXPORT_ATTRS +
                    COMPUTED_BOOKING_EXPORT_ATTRS.keys())

        bookings_soup = get_bookings_soup(context)

        # First, filter by allowed vendor areas
        vendor_uids = get_vendor_uids_for()
        query_b = Any('vendor_uid', vendor_uids)

        # Second, query for the buyable
        query_cat = {}
        query_cat['object_provides'] = IBuyable.__identifier__
        query_cat['path'] = '/'.join(context.getPhysicalPath())
        cat = getToolByName(context, 'portal_catalog')
        res = cat(**query_cat)
        buyable_uids = [IUUID(it.getObject()) for it in res]

        query_b = query_b & Any('buyable_uid', buyable_uids)

        all_orders = {}
        for booking in bookings_soup.query(query_b):
            booking_attrs = []
            # booking export attrs
            for attr_name in BOOKING_EXPORT_ATTRS:
                val = self.export_val(booking, attr_name)
                booking_attrs.append(val)
            # computed booking export attrs
            for attr_name in COMPUTED_BOOKING_EXPORT_ATTRS:
                cb = COMPUTED_BOOKING_EXPORT_ATTRS[attr_name]
                val = cb(context, booking)
                val = cleanup_for_csv(val)
                booking_attrs.append(val)

            # create order_attrs, if it doesn't exist
            order_uid = booking.attrs.get('order_uid')
            if order_uid not in all_orders:
                order = get_order(context, order_uid)
                order_data = OrderData(context,
                                       order=order,
                                       vendor_uids=vendor_uids)
                order_attrs = []
                # order export attrs
                for attr_name in ORDER_EXPORT_ATTRS:
                    val = self.export_val(order, attr_name)
                    order_attrs.append(val)
                # computed order export attrs
                for attr_name in COMPUTED_ORDER_EXPORT_ATTRS:
                    cb = COMPUTED_ORDER_EXPORT_ATTRS[attr_name]
                    val = cb(self.context, order_data)
                    val = cleanup_for_csv(val)
                    order_attrs.append(val)
                all_orders[order_uid] = order_attrs

            ex.writerow(all_orders[order_uid] + booking_attrs)

            # TODO: also set for contextual exports? i'd say no.
            # booking.attrs['exported'] = True
            # bookings_soup.reindex(booking)

        ret = sio.getvalue()
        sio.close()
        return ret
