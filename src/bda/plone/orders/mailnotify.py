# -*- coding: utf-8 -*-
from Products.CMFPlone.utils import safe_unicode
from bda.plone.cart import ascur
from bda.plone.cart import get_catalog_brain
from bda.plone.checkout.interfaces import ICheckoutEvent
from bda.plone.checkout.interfaces import ICheckoutSettings
from bda.plone.orders import get_country_name
from bda.plone.orders import interfaces as ifaces
from bda.plone.orders import message_factory as _
from bda.plone.orders import vocabularies as vocabs
from bda.plone.orders.common import DT_FORMAT
from bda.plone.orders.common import OrderData
from bda.plone.orders.interfaces import IGlobalNotificationText
from bda.plone.orders.interfaces import IItemNotificationText
from bda.plone.orders.interfaces import INotificationSettings
from bda.plone.orders.interfaces import IPaymentText
from bda.plone.orders.mailtemplates import get_booking_cancelled_templates
from bda.plone.orders.mailtemplates import get_booking_reserved_to_ordered_templates  # noqa
from bda.plone.orders.mailtemplates import get_order_templates
from bda.plone.orders.mailtemplates import get_reservation_templates
from bda.plone.orders.mailtemplates import get_stock_threshold_reached_templates  # noqa
from email.utils import formataddr
from plone import api
from zope.component.hooks import getSite
from zope.globalrequest import getRequest
from zope.i18n import translate
import logging
import textwrap
from zope.globalrequest import getRequest

import requests
import logging
import textwrap
import uuid
import smtplib
import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication

from collective.sendaspdf.utils import extract_from_url, update_relative_url, find_filename, md5_hash
from collective.sendaspdf.transforms import wk
from random import randint

from bda.plone.cart import is_ticket


logger = logging.getLogger('bda.plone.orders')

NOTIFICATIONS = {}

LIVE_URL = "http://tickets.teylersmuseum.nl"

POSSIBLE_TEMPLATE_CALLBACKS = [
    'booking_cancelled_title',
    'booking_reserved_to_ordered_title',
    'global_text',
    'item_listing',
    'reserved_item_listing',
    'order_summary',
    'payment_text',
    'stock_threshold_reached_text',
]


# MAIL NOTIFICATION UTILITIES

def get_order_uid(event):
    uid = None
    if ICheckoutEvent.providedBy(event):
        uid = event.uid
    else:
        uid = event.order_uid
    return uid


def _indent(text, ind=5, width=80):
    """helper indents text"""
    wrapped = textwrap.fill(
        safe_unicode(text),
        width,
        initial_indent=ind * u' '
    )
    return wrapped


def _process_template_cb(name, tpls, args, context, order_data):
    cb_name = u'{0:s}_cb'.format(name)
    if cb_name in tpls:
        args[name] = tpls[cb_name](context, order_data)


def create_mail_listing(
    context,
    order_data,
    include_booking_states=(
        ifaces.STATE_FINISHED,
        ifaces.STATE_NEW,
        ifaces.STATE_PROCESSING
    )
):
    """Create item listing for notification mail.
    """
    lines = []
    for booking in order_data.bookings:
        state = safe_unicode(booking.attrs.get('state'))
        if state not in include_booking_states:
            continue
        brain = get_catalog_brain(context, booking.attrs['buyable_uid'])
        # fetch buyable
        try:
            buyable = brain.getObject()
        except:
            buyable = None
        # fetch buyable title
        title = safe_unicode(booking.attrs['title'])
        # fetch item_number
        item_number = u''
        if booking.attrs['item_number']:
            item_number = u' ({0})'.format(
                safe_unicode(booking.attrs['item_number']))
        # fetch buyable comment
        comment = safe_unicode(booking.attrs['buyable_comment'])
        if comment:
            title = u'{0} ({1})'.format(title, comment)
        # fetch currency
        currency = safe_unicode(booking.attrs['currency'])
        # fetch net
        net = booking.attrs['net']
        # build price
        price = u'{currency} {net: 0.2f}'.format(
            currency=currency,
            net=net
        )
        # XXX: discount
        state_text = u''
        if state == ifaces.STATE_RESERVED:
            state_text = u' ({0})'.format(vocabs.state_vocab()[state])
        line = u'{count: 4f} {title}{item_number} {state} {price}'.format(
            count=booking.attrs['buyable_count'],
            title=title,
            item_number=item_number,
            state=state_text,
            price=price,
        )
        lines.append(line)
        if comment:
            lines.append(_indent(u'({0})'.format(comment)))

        if buyable:
            notificationtext = IItemNotificationText(buyable)
            if state == ifaces.STATE_RESERVED:
                text = notificationtext.overbook_text
            elif state == ifaces.STATE_NEW:
                text = notificationtext.order_text
            else:
                text = None
            if text:
                lines.append(_indent(text))
        else:
            notificationtext = None
        
    return u'\n'.join(lines)


def create_reserved_item_listing(context, order_data):
    return create_mail_listing(
        context,
        order_data,
        include_booking_states=(ifaces.STATE_RESERVED)
    )


def create_order_summary(context, order_data):
    """Create summary for notification mail.
    """
    attrs = order_data.order.attrs
    cart_total = order_data.total
    # no costs at all
    if not cart_total:
        return u''
    lines = []
    request = getRequest()
    # currency
    currency = order_data.currency
    # cart net and vat
    cart_net = order_data.net
    if cart_net:
        # cart net
        order_summary_cart_net = _(
            'order_summary_cart_net',
            default=u'Net: ${value} ${currency}',
            mapping={
                'value': ascur(cart_net),
                'currency': currency,
            })
        lines.append(translate(order_summary_cart_net, context=request))
        # cart vat
        cart_vat = order_data.vat
        order_summary_cart_vat = _(
            'order_summary_cart_vat',
            default=u'VAT: ${value} ${currency}',
            mapping={
                'value': ascur(cart_vat),
                'currency': currency,
            })
        lines.append(translate(order_summary_cart_vat, context=request))
    # cart discount
    discount_net = order_data.discount_net
    if discount_net:
        # discount net
        order_summary_discount_net = _(
            'order_summary_discount_net',
            default=u'Discount Net: ${value} ${currency}',
            mapping={
                'value': ascur(discount_net),
                'currency': currency,
            })
        lines.append(translate(order_summary_discount_net, context=request))
        # discount vat
        discount_vat = order_data.discount_vat
        order_summary_discount_vat = _(
            'order_summary_discount_vat',
            default=u'Discount VAT: ${value} ${currency}',
            mapping={
                'value': ascur(discount_vat),
                'currency': currency,
            })
        lines.append(translate(order_summary_discount_vat, context=request))
        # discount total
        discount_total = discount_net + discount_vat
        order_summary_discount_total = _(
            'order_summary_discount_total',
            default=u'Discount Total: ${value} ${currency}',
            mapping={
                'value': ascur(discount_total),
                'currency': currency,
            })
        lines.append(translate(order_summary_discount_total, context=request))
    # shipping costs
    shipping_net = order_data.shipping_net
    if shipping_net:
        # shiping label
        shipping_label = attrs['shipping_label']
        order_summary_shipping_label = _(
            'order_summary_shipping_label',
            default=u'Shipping: ${label}',
            mapping={
                'label': translate(shipping_label, context=request),
            })
        lines.append(translate(order_summary_shipping_label, context=request))
        # shiping description
        shipping_description = attrs['shipping_description']
        lines.append(translate(shipping_description, context=request))
        # shiping net
        order_summary_shipping_net = _(
            'order_summary_shipping_net',
            default=u'Shipping Net: ${value} ${currency}',
            mapping={
                'value': ascur(shipping_net),
                'currency': currency,
            })
        lines.append(translate(order_summary_shipping_net, context=request))
        # shiping vat
        shipping_vat = order_data.shipping_vat
        order_summary_shipping_vat = _(
            'order_summary_shipping_vat',
            default=u'Shipping VAT: ${value} ${currency}',
            mapping={
                'value': ascur(shipping_vat),
                'currency': currency,
            })
        lines.append(translate(order_summary_shipping_vat, context=request))
        # shiping total
        shipping_total = shipping_net + shipping_vat
        order_summary_shipping_total = _(
            'order_summary_shipping_total',
            default=u'Shipping Total: ${value} ${currency}',
            mapping={
                'value': ascur(shipping_total),
                'currency': currency,
            })
        lines.append(translate(order_summary_shipping_total, context=request))
    # cart total
    order_summary_cart_total = _(
        'order_summary_cart_total',
        default=u'Total: ${value} ${currency}',
        mapping={
            'value': ascur(cart_total),
            'currency': currency,
        })
    lines.append(translate(order_summary_cart_total, context=request))
    summary_title = translate(
        _('order_summary_label', default=u'Summary:'), context=request)
    summary_text = u'\n'.join(lines)
    return u'\n{summary_title}\n{summary_text}\n'.format(
        summary_title=summary_title,
        summary_text=summary_text
    )


def create_global_text(context, order_data):
    order_state = order_data.state
    notifications = set()
    for booking in order_data.bookings:
        brain = get_catalog_brain(context, booking.attrs['buyable_uid'])
        try:
            buyable = brain.getObject()
            notificationtext = IGlobalNotificationText(buyable)
            if order_state in (ifaces.STATE_RESERVED, ifaces.STATE_MIXED):
                # XXX: might need custom text for MIXED state
                text = notificationtext.global_overbook_text
                if text:
                    notifications.add(text)
            elif order_state == ifaces.STATE_NEW:
                text = notificationtext.global_order_text
                if text:
                    notifications.add(text)
        except:
            pass
    global_text = u'\n\n'.join(notifications)
    if global_text.strip():
        return u'\n\n{global_text}\n'.format(global_text=global_text.strip())
    return u''


def create_payment_text(context, order_data):
    payment = order_data.order.attrs['payment_method']
    payment_text = IPaymentText(getSite()).payment_text(payment)
    if payment_text.strip():
        return u'\n\n{payment_text}\n'.format(payment_text=payment_text.strip())  # noqa
    return u''


def create_mail_body(templates, context, order_data):
    """Creates a rendered mail body

    templates
        Dict with a bunch of cbs and the body template itself.

    context
        Some object in Plone which can be used as a context to acquire from

    order_data
        Order-data instance.
    """

    tickets = is_ticket(context)

    lang = context.restrictedTraverse('@@plone_portal_state').language()
    attrs = order_data.order.attrs
    arguments = dict(
        (safe_unicode(key), safe_unicode(value))
        for (key, value) in attrs.items()
    )

    arguments['personal_data.company'] = ''
    arguments['personal_data.phone'] = ''
    arguments['billing_address.street'] = ''

    arguments['portal_url'] = getSite().absolute_url()
    arguments['date'] = attrs['created'].strftime(DT_FORMAT)
    salutation = translate(attrs['personal_data.gender'],
                           domain='bda.plone.checkout',
                           target_language=lang)
    arguments['salutation'] = salutation

    if not tickets:
        # Change country code to translated country name
        if arguments.get('billing_address.country', None):
            arguments['billing_address.country'] = get_country_name(arguments['billing_address.country'], lang=lang)  # noqa

        if arguments.get('delivery_address.country', None):
            arguments['delivery_address.country'] = get_country_name(arguments['delivery_address.country'], lang=lang)  # noqa

        # todo: next should be a cb
        arguments['delivery_address'] = ''
        if attrs.get('delivery_address.alternative_delivery', ''):
            delivery_address_template = templates.get('delivery_address', None)
            if delivery_address_template:
                # If no template is defined, it might not be useful in this context
                # (e.g. cancelling bookings)
                arguments['delivery_address'] = delivery_address_template % arguments  # noqa

    if tickets:
        base_url = context.portal_url()
        params = "?order_id=%s" %(str(attrs['uid']))
        download_as_pdf_link = "%s/%s/download_as_pdf?page_url=%s/%s/tickets/etickets%s" %(base_url, lang, base_url, lang, params)
        download_link = download_as_pdf_link

        email_confirmation_text = ""

        if email_confirmation_text:
            #email_temp = templates['event_ticket']
            #body_template = email_temp %(email_confirmation_text)
            body_template = templates['ticket']
        else:
            body_template = templates['ticket']

        arguments["download_link"] = download_link
    else:
        body_template = templates['body']

    for name in POSSIBLE_TEMPLATE_CALLBACKS:
        _process_template_cb(
            name,
            templates,
            arguments,
            context,
            order_data
        )
    return body_template % arguments


# DO NOTIFY

class MailNotify(object):
    """Mail notifyer.
    """

    def __init__(self, context, order_data=None):
        self.context = context
        self.request = getRequest()
        self.order_data = order_data
        self.settings = INotificationSettings(self.context)
        self.tempdir = '/tmp/'
        self.salt = 'salt_as_pdf'

    def generate_filename_prefix(self):
        return ''

    def generate_temp_filename(self):
        prefix = self.generate_filename_prefix()
        now = datetime.datetime.now()
        # Ok that might not be the best timestamp system, but it's
        # enough for our needs.
        timestamp = '-'.join([
            ''.join([str(x) for x in now.timetuple()]),
            str(now.microsecond),
            str(randint(10000, 99999))])

        filename = prefix + timestamp
        return find_filename(self.tempdir, filename)

    def generate_pdf_file(self, source):
        """ Generates a PDF file from the given source
        (string containing the HTML source of a page).
        """
        url = self.context.absolute_url()

        filename = self.generate_temp_filename()
        if not filename:
            self.send_failed(self.order_data.order, "PDF filename failed to generated.")
            return False

        print_css = (False)

        export_file, err = wk.html_to_pdf(
            source,
            self.tempdir,
            filename,
            url,
            print_css,
            ['0', '--margin-top', '0', '--margin-bottom', '0', '--margin-left', '0', '--margin-right'])

        if err:
            self.send_failed(self.order_data.order, "PDF creation failed.")
            return False

        return export_file


    def make_pdf(self):
        context_url = self.context.absolute_url()

        uid = self.order_data.order.attrs['uid']
        link = "%s/%s/tickets/etickets?order_id=%s" %(LIVE_URL, getattr(self.context, 'language', 'nl'), uid)

        source = link
        if not source:
            # XXX: need to send email
            self.send_failed(self.order_data.order, "Page source failed to generated.")
            return False
    
        pdf_file = self.generate_pdf_file(source)
        return pdf_file

    def download_file(self, url):
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        opener.addheaders.append(('User-Agent', 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.11) Gecko/20101012 Firefox/3.6.11'))
        request = urllib2.Request(url)
        try:
            f = opener.open(request, timeout=120)
            data = f.read()
        except:
            raise
        return data

    def send_failed(self, data, msg=""):
        receiver = "andre@itsnotthatkind.org"
        mailfrom = "andre@intk.com"
        timestamp = datetime.datetime.today().isoformat()

        if data != None:
            order_uid = data.attrs['uid']
            ordernumber = data.attrs['ordernumber']
            first_name = data.attrs['personal_data.firstname']
            last_name = data.attrs['personal_data.lastname']
            email = data.attrs['personal_data.email']

            subject = "Order %s failed to generate pdf." %(ordernumber)
            message = "\n[%s] Ordernumber %s\nOrder uid: %s\n\nPersonal details:\nFirst name: %s\nLast name: %s\nE-mail: %s\n\nError exception: %s" %(str(timestamp), ordernumber, order_uid, first_name, last_name, email, msg)
        else:
            subject = "Order Unknown failed to generate pdf."
            message = "Order unknown failed to generate pdf.\nTimestamp: %s" %(str(timestamp))

        api.portal.send_email(
            recipient=receiver,
            sender=mailfrom,
            subject=subject,
            body=message
        )

    def send(self, subject, message, receiver):
        shop_manager_address = self.settings.admin_email
        if not shop_manager_address:
            raise ValueError('Shop manager address is missing in settings.')
        shop_manager_name = self.settings.admin_name
        if shop_manager_name:
            from_name = shop_manager_name
            mailfrom = formataddr((from_name, shop_manager_address))
        else:
            mailfrom = shop_manager_address


        tickets = 'tickets' in self.context.absolute_url()
        tickets = True

        if not tickets:
            api.portal.send_email(
                recipient=receiver,
                sender=mailfrom,
                subject=subject,
                body=message,
            )
        else:
            text = MIMEMultipart('alternative')
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = mailfrom

            pdfAttachment = None

            try:
                if receiver != shop_manager_address:
                    pdf_file = self.make_pdf()
                    if pdf_file:
                        data = pdf_file.read()
                        pdf_file.close()

                        if data:
                            pdfAttachment = MIMEApplication(data, _subtype = "pdf")
                            pdfAttachment.add_header('content-disposition', 'attachment', filename='e-tickets.pdf')

            except Exception, e:
                error_msg = str(e)
                self.send_failed(self.order_data.order, error_msg)
                pass

            if pdfAttachment:
                text.attach(MIMEText(message, 'html', 'utf-8'))
                msg.attach(text)
                msg.attach(pdfAttachment)
            else:
                failed_text = "<p><a href='%s/%s/download_as_pdf?page_url=%s/%s/tickets/etickets?order_id=%s'>Download e-ticket(s)</a></p>"%(LIVE_URL, getattr(self.context, 'language', 'nl'), LIVE_URL, getattr(self.context, 'language', 'nl'), self.order_data.order.attrs['uid'])
                message = str(message) + str(failed_text)
                text.attach(MIMEText(message, 'html', 'utf-8'))
                msg.attach(text)

            s = smtplib.SMTP('127.0.0.1')
            s.sendmail(mailfrom, receiver, msg.as_string())
            s.quit()


def do_notify(context, order_data, templates, receiver):
    attrs = order_data.order.attrs

    tickets = is_ticket(context)

    if tickets:
        subject = templates['subject']
    else:
        subject = templates['subject'] % attrs['ordernumber']

    subject = templates['subject'] % attrs['ordernumber']

    message = create_mail_body(templates, context, order_data)
    
    mail_notify = MailNotify(context, order_data)
    try:
        mail_notify.send(subject, message, receiver)
    except Exception:
        msg = translate(
            _('email_sending_failed',
              default=u'Failed to send notification to ${receiver}',
              mapping={'receiver': receiver}))
        api.portal.show_message(message=msg, request=context.REQUEST)
        logger.exception("Email could not be sent.")


def do_notify_customer(context, order_data, templates):
    customer_address = order_data.order.attrs['personal_data.email']
    do_notify(context, order_data, templates, customer_address)


def do_notify_shopmanager(context, order_data, templates):
    shop_manager_address = INotificationSettings(context).admin_email
    do_notify(context, order_data, templates, shop_manager_address)


# ORDER SUCCSESS


def dispatch_notify_order_success(event):
    for func in NOTIFICATIONS['order_success']:
        func(event)


def notify_order_success(event, who=None):
    """Send notification mail after order succeeded.
    """
    if who not in ['customer', 'shopmanager']:
        raise ValueError(
            'kw "who" mus be one out of ("customer", "shopmanager")'
        )
    order_data = OrderData(event.context, uid=get_order_uid(event))
    templates = dict()
    state = order_data.state
    if state in (ifaces.STATE_RESERVED, ifaces.STATE_MIXED):
        templates.update(get_reservation_templates(event.context))
        templates['reserved_item_listing_cb'] = create_reserved_item_listing
    else:
        templates.update(get_order_templates(event.context))
    templates['item_listing_cb'] = create_mail_listing
    templates['order_summary_cb'] = create_order_summary
    templates['global_text_cb'] = create_global_text
    templates['payment_text_cb'] = create_payment_text
    if who == "customer":
        do_notify_customer(event.context, order_data, templates)
    else:
        do_notify_shopmanager(event.context, order_data, templates)


def notify_order_success_customer(event):
    notify_order_success(event, who="customer")


def notify_order_success_shopmanager(event):
    notify_order_success(event, who="shopmanager")


NOTIFICATIONS['order_success'] = []
NOTIFICATIONS['order_success'].append(notify_order_success_customer)
NOTIFICATIONS['order_success'].append(notify_order_success_shopmanager)


# CHECKOUT SUCCSESS

def dispatch_notify_checkout_success(event):
    for func in NOTIFICATIONS['checkout_success']:
        func(event)


def notify_checkout_success_customer(event):
    """Send notification mail after checkout succeed.
    """
    # if skip payment, do notification
    checkout_settings = ICheckoutSettings(event.context)
    if checkout_settings.skip_payment(get_order_uid(event)):
        notify_order_success(event, who="customer")


def notify_checkout_success_shopmanager(event):
    """Send notification mail after checkout succeed.
    """
    # if skip payment, do notification
    checkout_settings = ICheckoutSettings(event.context)
    if checkout_settings.skip_payment(get_order_uid(event)):
        notify_order_success(event, who="shopmanager")


NOTIFICATIONS['checkout_success'] = []
NOTIFICATIONS['checkout_success'].append(notify_checkout_success_customer)
NOTIFICATIONS['checkout_success'].append(notify_checkout_success_shopmanager)


# PAYMENT SUCCESS


def dispatch_notify_payment_success(event):
    for func in NOTIFICATIONS['payment_success']:
        func(event)


def notify_payment_success_customer(event):
    """Send notification mail after payment succeed.
    """
    notify_order_success(event, who="customer")


def notify_payment_success_shopmanager(event):
    """Send notification mail after payment succeed.
    """
    notify_order_success(event, who="shopmanager")


NOTIFICATIONS['payment_success'] = []
NOTIFICATIONS['payment_success'].append(notify_payment_success_customer)
NOTIFICATIONS['payment_success'].append(notify_payment_success_shopmanager)


# BOOKING CANCELLED

BOOKING_CANCELLED_TITLE_ATTRIBUTE = 'title'


def dispatch_notify_booking_cancelled(event):
    for func in NOTIFICATIONS['booking_cancelled']:
        func(event)


class BookingCancelledTitleCB(object):

    def __init__(self, event):
        self.event = event

    def __call__(self, *args):
        return self.event.booking_attrs[BOOKING_CANCELLED_TITLE_ATTRIBUTE]


def notify_booking_cancelled(event, who=None):
    """Send notification mail after booking was cancelled.
    """
    order_data = OrderData(event.context, uid=get_order_uid(event))
    templates = dict()
    templates.update(get_booking_cancelled_templates(event.context))
    templates['booking_cancelled_title_cb'] = BookingCancelledTitleCB(event)
    if who == "customer":
        do_notify_customer(event.context, order_data, templates)
    elif who == 'shopmanager':
        do_notify_shopmanager(event.context, order_data, templates)
    else:
        raise ValueError(
            'kw "who" mus be one out of ("customer", "shopmanager")'
        )


def notify_booking_cancelled_customer(event):
    notify_booking_cancelled(event, who="customer")


def notify_booking_cancelled_shopmanager(event):
    notify_booking_cancelled(event, who="shopmanager")


NOTIFICATIONS['booking_cancelled'] = []
#NOTIFICATIONS['booking_cancelled'].append(notify_booking_cancelled_customer)
#NOTIFICATIONS['booking_cancelled'].append(notify_booking_cancelled_shopmanager)


# BOOKING RESERVED TO ORDERED
def dispatch_notify_booking_reserved_to_ordered(event):
    for func in NOTIFICATIONS['booking_reserved_to_ordered']:
        func(event)


BookingReservedToOrderedTitleCB = BookingCancelledTitleCB


def notify_booking_reserved_to_ordered(event, who=None):
    """Send notification mail after booking was changed from reserved to ordered.
    """
    order_data = OrderData(event.context, uid=get_order_uid(event))
    templates = dict()
    templates.update(get_booking_reserved_to_ordered_templates(event.context))
    templates['booking_reserved_to_ordered_title_cb'] = BookingReservedToOrderedTitleCB(event)  # noqa
    if who == "customer":
        do_notify_customer(event.context, order_data, templates)
    elif who == 'shopmanager':
        do_notify_shopmanager(event.context, order_data, templates)
    else:
        raise ValueError(
            'kw "who" mus be one out of ("customer", "shopmanager")'
        )


def notify_booking_reserved_to_ordered_customer(event):
    notify_booking_reserved_to_ordered(event, who="customer")


def notify_booking_reserved_to_ordered_shopmanager(event):
    notify_booking_reserved_to_ordered(event, who="shopmanager")


NOTIFICATIONS['booking_reserved_to_ordered'] = []
NOTIFICATIONS['booking_reserved_to_ordered'].append(notify_booking_reserved_to_ordered_customer)  # noqa
NOTIFICATIONS['booking_reserved_to_ordered'].append(notify_booking_reserved_to_ordered_shopmanager)  # noqa


# STOCK THRESHOLD REACHED

def dispatch_notify_stock_threshold_reached(event):
    for func in NOTIFICATIONS['stock_threshold_reached']:
        func(event)


class StockThresholdReachedCB(object):

    def __init__(self, event):
        self.event = event

    def __call__(self, *args):
        stock_threshold_reached_text = ""
        items = self.event.stock_threshold_reached_items
        for item_attrs in items:
            title = item_attrs['title']
            remaining_stock = item_attrs['remaining_stock_available']
            stock_threshold_reached_text += u"{0} (Remaining stock: {1})\n".format(  # noqa
                title,
                remaining_stock
            )
        return stock_threshold_reached_text


def notify_stock_threshold_reached(event):
    """Send notification mail when item is getting out of stock.
    """
    order_data = OrderData(event.context, uid=get_order_uid(event))
    templates = dict()
    templates.update(get_stock_threshold_reached_templates(event.context))
    templates['stock_threshold_reached_text_cb'] = \
        StockThresholdReachedCB(event)
    do_notify_shopmanager(event.context, order_data, templates)


NOTIFICATIONS['stock_threshold_reached'] = []
NOTIFICATIONS['stock_threshold_reached'].append(notify_stock_threshold_reached)


