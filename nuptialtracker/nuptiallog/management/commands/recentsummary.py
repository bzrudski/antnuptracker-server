from django.core.management.base import BaseCommand, CommandError
from nuptiallog.models import Flight, FlightUser
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.utils.timezone import now as time, timedelta
from django.template.loader import render_to_string
from nuptialtracker.settings import EMAIL_HOST_USER

class Command(BaseCommand):
    help = 'Sends an email with statistics to the host email address'

    def handle(self, *args, **options):
        total_flights = Flight.objects.count()
        yesterday = time() - timedelta(days=1)
        yesterday_flights = Flight.objects.filter(dateRecorded__gte=yesterday).count()
        user_count = User.objects.count()
        professional_count = User.objects.filter(flightuser__professional=True).count()
        professional_users = User.objects.filter(flightuser__professional=True, date_joined__gte=yesterday)

        subject = "AntNupTracker Stats"
        message = render_to_string('nuptiallog/UsersSummaryEmail.html', {
            'total_flights' : total_flights,
            'yesterday_flights' : yesterday_flights,
            'user_count'    : user_count,
            'professional_count'    : professional_count,
            'professional_users'    : professional_users,
            'date'  : yesterday
        })

        email = EmailMessage(subject, message, to=[EMAIL_HOST_USER])
        email.content_subtype = 'html'

        try:
            email.send()
        except:
            raise CommandError("Unable to send email to the host user")

        self.stdout.write("Sent summary email!")
