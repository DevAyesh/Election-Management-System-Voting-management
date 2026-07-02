from django.contrib import admin
from .models import PollingStation, TempVoterId, AuditLog
import secrets


# ---------------------------------------------------------------------------
# Polling Station Admin
# ---------------------------------------------------------------------------

@admin.action(description='Regenerate login key for selected stations')
def regenerate_login_key(modeladmin, request, queryset):
    for station in queryset:
        station.login_key = secrets.token_urlsafe(32)
        station.save(update_fields=['login_key'])
    modeladmin.message_user(request, f'Regenerated keys for {queryset.count()} station(s).')


@admin.register(PollingStation)
class PollingStationAdmin(admin.ModelAdmin):
    list_display  = ('district_number', 'district_name', 'division_code', 'division_name',
                     'masked_key', 'is_active', 'created_at')
    list_filter   = ('district_name', 'is_active')
    search_fields = ('district_name', 'division_name', 'login_key')
    ordering      = ('district_number', 'division_code')
    readonly_fields = ('created_at',)
    actions       = [regenerate_login_key]

    fieldsets = (
        ('Location', {
            'fields': ('district_number', 'district_name', 'division_code', 'division_name'),
        }),
        ('Credentials', {
            'fields': ('login_key', 'is_active'),
        }),
        ('Meta', {
            'fields': ('created_at',),
        }),
    )

    def masked_key(self, obj):
        """Show only first 8 chars of the key for security."""
        return obj.login_key[:8] + '***' if obj.login_key else '—'
    masked_key.short_description = 'Login Key (partial)'


# ---------------------------------------------------------------------------
# Temporary Voter ID Admin
# ---------------------------------------------------------------------------

@admin.register(TempVoterId)
class TempVoterIdAdmin(admin.ModelAdmin):
    list_display  = ('voter_id', 'full_name', 'district', 'division', 'has_voted', 'created_at')
    list_filter   = ('district', 'division', 'has_voted')
    search_fields = ('voter_id', 'full_name')
    ordering      = ('-created_at',)
    readonly_fields = ('created_at',)


# ---------------------------------------------------------------------------
# Audit Log Admin (read-only)
# ---------------------------------------------------------------------------

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('timestamp', 'event_type', 'station_name', 'ip_address', 'details_short')
    list_filter   = ('event_type',)
    search_fields = ('station_name', 'ip_address', 'details')
    ordering      = ('-timestamp',)
    readonly_fields = ('event_type', 'station_name', 'ip_address', 'details', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def details_short(self, obj):
        return obj.details[:80] + ('…' if len(obj.details) > 80 else '')
    details_short.short_description = 'Details'
