from django.core.management.base import BaseCommand

from portfolio.account_lifecycle import sweep


class Command(BaseCommand):
    help = "Delete accounts whose portfolios nobody has visited for a year (the site owner's and admin accounts never)."

    def handle(self, *args, **options):
        self.stdout.write(f"Deleted {sweep()} inactive account(s).")
