"""
Management command: seed_polling_stations
Usage:  python manage.py seed_polling_stations

Populates the PollingStation table with all 154 polling divisions from
Section 9(3) of the Registration of Electors Act No. 44 of 1980.

Safe to re-run — uses get_or_create so existing records are preserved.
Prints the login key for newly created stations.
"""
import secrets
from django.core.management.base import BaseCommand
from voting.models import PollingStation


DIVISIONS = [
    # (district_number, district_name, division_code, division_name)
    # 01 — Colombo (15)
    (1,  'Colombo',      'A', 'Colombo North'),
    (1,  'Colombo',      'B', 'Colombo Central'),
    (1,  'Colombo',      'C', 'Borella'),
    (1,  'Colombo',      'D', 'Colombo East'),
    (1,  'Colombo',      'E', 'Colombo West'),
    (1,  'Colombo',      'F', 'Dehiwala'),
    (1,  'Colombo',      'G', 'Ratmalana'),
    (1,  'Colombo',      'H', 'Kolonnawa'),
    (1,  'Colombo',      'I', 'Kotte'),
    (1,  'Colombo',      'J', 'Kaduwela'),
    (1,  'Colombo',      'K', 'Avissawella'),
    (1,  'Colombo',      'L', 'Homagama'),
    (1,  'Colombo',      'M', 'Maharagama'),
    (1,  'Colombo',      'N', 'Kesbewa'),
    (1,  'Colombo',      'O', 'Moratuwa'),
    # 02 — Gampaha (13)
    (2,  'Gampaha',      'A', 'Wattala'),
    (2,  'Gampaha',      'B', 'Negombo'),
    (2,  'Gampaha',      'C', 'Katana'),
    (2,  'Gampaha',      'D', 'Divulapitiya'),
    (2,  'Gampaha',      'E', 'Mirigama'),
    (2,  'Gampaha',      'F', 'Minuwangoda'),
    (2,  'Gampaha',      'G', 'Attanagalla'),
    (2,  'Gampaha',      'H', 'Gampaha'),
    (2,  'Gampaha',      'I', 'Ja-Ela'),
    (2,  'Gampaha',      'J', 'Mahara'),
    (2,  'Gampaha',      'K', 'Dompe'),
    (2,  'Gampaha',      'L', 'Biyagama'),
    (2,  'Gampaha',      'M', 'Kelaniya'),
    # 03 — Kalutara (8)
    (3,  'Kalutara',     'A', 'Panadura'),
    (3,  'Kalutara',     'B', 'Bandaragama'),
    (3,  'Kalutara',     'C', 'Horana'),
    (3,  'Kalutara',     'D', 'Bulathsinhala'),
    (3,  'Kalutara',     'E', 'Matugama'),
    (3,  'Kalutara',     'F', 'Kalutara'),
    (3,  'Kalutara',     'G', 'Beruwala'),
    (3,  'Kalutara',     'H', 'Agalawatta'),
    # 04 — Kandy (13)
    (4,  'Kandy',        'A', 'Galagedara'),
    (4,  'Kandy',        'B', 'Harispattuwa'),
    (4,  'Kandy',        'C', 'Pathadumbara'),
    (4,  'Kandy',        'D', 'Udadumbara'),
    (4,  'Kandy',        'E', 'Teldeniya'),
    (4,  'Kandy',        'F', 'Kundasale'),
    (4,  'Kandy',        'G', 'Hewaheta'),
    (4,  'Kandy',        'H', 'Senkadagala'),
    (4,  'Kandy',        'I', 'Kandy'),
    (4,  'Kandy',        'J', 'Yatinuwara'),
    (4,  'Kandy',        'K', 'Udanuwara'),
    (4,  'Kandy',        'L', 'Gampola'),
    (4,  'Kandy',        'M', 'Nawalapitiya'),
    # 05 — Matale (4)
    (5,  'Matale',       'A', 'Dambulla'),
    (5,  'Matale',       'B', 'Laggala'),
    (5,  'Matale',       'C', 'Matale'),
    (5,  'Matale',       'D', 'Rattota'),
    # 06 — Nuwara Eliya (4)
    (6,  'Nuwara Eliya', 'A', 'Nuwara Eliya'),
    (6,  'Nuwara Eliya', 'B', 'Kotmale'),
    (6,  'Nuwara Eliya', 'C', 'Hanguranketha'),
    (6,  'Nuwara Eliya', 'D', 'Walapane'),
    # 07 — Galle (10)
    (7,  'Galle',        'A', 'Balapitiya'),
    (7,  'Galle',        'B', 'Ambalangoda'),
    (7,  'Galle',        'C', 'Karandeniya'),
    (7,  'Galle',        'D', 'Bentara-Elpitiya'),
    (7,  'Galle',        'E', 'Hiniduma'),
    (7,  'Galle',        'F', 'Baddegama'),
    (7,  'Galle',        'G', 'Ratgama'),
    (7,  'Galle',        'H', 'Galle'),
    (7,  'Galle',        'I', 'Akmeemana'),
    (7,  'Galle',        'J', 'Habaraduwa'),
    # 08 — Matara (7)
    (8,  'Matara',       'A', 'Deniyaya'),
    (8,  'Matara',       'B', 'Hakmana'),
    (8,  'Matara',       'C', 'Akuressa'),
    (8,  'Matara',       'D', 'Kamburupitiya'),
    (8,  'Matara',       'E', 'Devinuwara'),
    (8,  'Matara',       'F', 'Matara'),
    (8,  'Matara',       'G', 'Weligama'),
    # 09 — Hambantota (4)
    (9,  'Hambantota',   'A', 'Mulkirigala'),
    (9,  'Hambantota',   'B', 'Beliatta'),
    (9,  'Hambantota',   'C', 'Tangalle'),
    (9,  'Hambantota',   'D', 'Tissamaharamaya'),
    # 10 — Jaffna (11)
    (10, 'Jaffna',       'A', 'Kayts'),
    (10, 'Jaffna',       'B', 'Waddukkoddai'),
    (10, 'Jaffna',       'C', 'Kankasanturai'),
    (10, 'Jaffna',       'D', 'Manipai'),
    (10, 'Jaffna',       'E', 'Kopai'),
    (10, 'Jaffna',       'F', 'Uduppidi'),
    (10, 'Jaffna',       'G', 'Point Pedro'),
    (10, 'Jaffna',       'H', 'Chawakachcheri'),
    (10, 'Jaffna',       'I', 'Nallur'),
    (10, 'Jaffna',       'J', 'Jaffna'),
    (10, 'Jaffna',       'K', 'Kilinochchi'),
    # 11 — Vanni (3)
    (11, 'Vanni',        'A', 'Mannar'),
    (11, 'Vanni',        'B', 'Vavuniya'),
    (11, 'Vanni',        'C', 'Mullaitivu'),
    # 12 — Batticaloa (3)
    (12, 'Batticaloa',   'A', 'Kalkudah'),
    (12, 'Batticaloa',   'B', 'Batticaloa'),
    (12, 'Batticaloa',   'C', 'Padiruppu'),
    # 13 — Digamadulla (4)
    (13, 'Digamadulla',  'A', 'Ampara'),
    (13, 'Digamadulla',  'B', 'Samanturai'),
    (13, 'Digamadulla',  'C', 'Kalmunai'),
    (13, 'Digamadulla',  'D', 'Potuvil'),
    # 14 — Trincomalee (3)
    (14, 'Trincomalee',  'A', 'Seruwila'),
    (14, 'Trincomalee',  'B', 'Trincomalee'),
    (14, 'Trincomalee',  'C', 'Mutur'),
    # 15 — Kurunegala (14)
    (15, 'Kurunegala',   'A', 'Galgamuwa'),
    (15, 'Kurunegala',   'B', 'Nikaweratiya'),
    (15, 'Kurunegala',   'C', 'Yapahuwa'),
    (15, 'Kurunegala',   'D', 'Hiriyala'),
    (15, 'Kurunegala',   'E', 'Wariyapola'),
    (15, 'Kurunegala',   'F', 'Panduwasnuwara'),
    (15, 'Kurunegala',   'G', 'Bingiriya'),
    (15, 'Kurunegala',   'H', 'Katugampola'),
    (15, 'Kurunegala',   'I', 'Kuliyapitiya'),
    (15, 'Kurunegala',   'J', 'Dambadeniya'),
    (15, 'Kurunegala',   'K', 'Polgahawela'),
    (15, 'Kurunegala',   'L', 'Kurunegala'),
    (15, 'Kurunegala',   'M', 'Mawathagama'),
    (15, 'Kurunegala',   'N', 'Dodangaslanda'),
    # 16 — Puttalam (5)
    (16, 'Puttalam',     'A', 'Puttalam'),
    (16, 'Puttalam',     'B', 'Anamaduwa'),
    (16, 'Puttalam',     'C', 'Chillaw'),
    (16, 'Puttalam',     'D', 'Nattandiya'),
    (16, 'Puttalam',     'E', 'Wennappuwa'),
    # 17 — Anuradhapura (7)
    (17, 'Anuradhapura', 'A', 'Medawachchiya'),
    (17, 'Anuradhapura', 'B', 'Horowpothana'),
    (17, 'Anuradhapura', 'C', 'Anuradhapura East'),
    (17, 'Anuradhapura', 'D', 'Anuradhapura West'),
    (17, 'Anuradhapura', 'E', 'Kalawewa'),
    (17, 'Anuradhapura', 'F', 'Mihintale'),
    (17, 'Anuradhapura', 'G', 'Kekirawa'),
    # 18 — Polonnaruwa (3)
    (18, 'Polonnaruwa',  'A', 'Minneriya'),
    (18, 'Polonnaruwa',  'B', 'Medirigiriya'),
    (18, 'Polonnaruwa',  'C', 'Polonnaruwa'),
    # 19 — Badulla (9)
    (19, 'Badulla',      'A', 'Mahiyanganaya'),
    (19, 'Badulla',      'B', 'Wiyaluwa'),
    (19, 'Badulla',      'C', 'Passara'),
    (19, 'Badulla',      'D', 'Badulla'),
    (19, 'Badulla',      'E', 'Hali-Ela'),
    (19, 'Badulla',      'F', 'Uva Paranagama'),
    (19, 'Badulla',      'G', 'Welimada'),
    (19, 'Badulla',      'H', 'Bandarawela'),
    (19, 'Badulla',      'I', 'Haputale'),
    # 20 — Monaragala (3)
    (20, 'Monaragala',   'A', 'Bibila'),
    (20, 'Monaragala',   'B', 'Monaragala'),
    (20, 'Monaragala',   'C', 'Wellawaya'),
    # 21 — Ratnapura (8)
    (21, 'Ratnapura',    'A', 'Eheliyagoda'),
    (21, 'Ratnapura',    'B', 'Ratnapura'),
    (21, 'Ratnapura',    'C', 'Pelmadulla'),
    (21, 'Ratnapura',    'D', 'Balangoda'),
    (21, 'Ratnapura',    'E', 'Rakwana'),
    (21, 'Ratnapura',    'F', 'Nivithigala'),
    (21, 'Ratnapura',    'G', 'Kalawana'),
    (21, 'Ratnapura',    'H', 'Kolonna'),
    # 22 — Kegalle (9)
    (22, 'Kegalle',      'A', 'Dedigama'),
    (22, 'Kegalle',      'B', 'Galigamuwa'),
    (22, 'Kegalle',      'C', 'Kegalle'),
    (22, 'Kegalle',      'D', 'Rambukkana'),
    (22, 'Kegalle',      'E', 'Mawanella'),
    (22, 'Kegalle',      'F', 'Aranayake'),
    (22, 'Kegalle',      'G', 'Yatiyantota'),
    (22, 'Kegalle',      'H', 'Ruwanwella'),
    (22, 'Kegalle',      'I', 'Deraniyagala'),
]


class Command(BaseCommand):
    help = 'Seed all 154 polling divisions with unique login keys (safe to re-run)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-keys',
            action='store_true',
            help='Print the full login key for each station (for handover documents)',
        )

    def handle(self, *args, **options):
        show_keys = options['show_keys']
        created_count  = 0
        existing_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nSeeding {len(DIVISIONS)} polling divisions...\n'
        ))

        for district_num, district_name, code, division_name in DIVISIONS:
            station, created = PollingStation.objects.get_or_create(
                district_number=district_num,
                division_code=code,
                defaults={
                    'district_name': district_name,
                    'division_name': division_name,
                    'login_key':     secrets.token_urlsafe(32),
                    'is_active':     True,
                },
            )

            if created:
                created_count += 1
                key_display = station.login_key if show_keys else station.login_key[:8] + '***'
                self.stdout.write(
                    f"  [NEW]  {district_num:02d}-{code}  "
                    f"{district_name:<15} / {division_name:<25}  key: {key_display}"
                )
            else:
                existing_count += 1
                if show_keys:
                    self.stdout.write(
                        f"  [OK]   {district_num:02d}-{code}  "
                        f"{district_name:<15} / {division_name:<25}  key: {station.login_key}"
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done: {created_count} created, {existing_count} already existed.'
        ))
        if not show_keys and created_count:
            self.stdout.write(
                self.style.WARNING(
                    'Tip: run with --show-keys to print full login keys for distribution.'
                )
            )
