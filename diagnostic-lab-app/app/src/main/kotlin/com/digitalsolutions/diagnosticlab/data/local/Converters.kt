package com.digitalsolutions.diagnosticlab.data.local

import androidx.room.TypeConverter
import com.digitalsolutions.diagnosticlab.domain.model.*

class Converters {

    @TypeConverter fun fromUserRole(v: UserRole) = v.name
    @TypeConverter fun toUserRole(v: String) = UserRole.valueOf(v)

    @TypeConverter fun fromRelation(v: Relation) = v.name
    @TypeConverter fun toRelation(v: String) = Relation.valueOf(v)

    @TypeConverter fun fromBookingStatus(v: BookingStatus) = v.name
    @TypeConverter fun toBookingStatus(v: String) = BookingStatus.valueOf(v)

    @TypeConverter fun fromAssignmentStatus(v: AssignmentStatus) = v.name
    @TypeConverter fun toAssignmentStatus(v: String) = AssignmentStatus.valueOf(v)

    @TypeConverter fun fromPaymentMethod(v: PaymentMethod) = v.name
    @TypeConverter fun toPaymentMethod(v: String) = PaymentMethod.valueOf(v)

    @TypeConverter fun fromPaymentStatus(v: PaymentStatus) = v.name
    @TypeConverter fun toPaymentStatus(v: String) = PaymentStatus.valueOf(v)

    @TypeConverter fun fromSampleStatus(v: SampleStatus) = v.name
    @TypeConverter fun toSampleStatus(v: String) = SampleStatus.valueOf(v)

    @TypeConverter fun fromSampleRejectionReason(v: SampleRejectionReason?) = v?.name
    @TypeConverter fun toSampleRejectionReason(v: String?) = v?.let { SampleRejectionReason.valueOf(it) }

    @TypeConverter fun fromReportStatus(v: ReportStatus) = v.name
    @TypeConverter fun toReportStatus(v: String) = ReportStatus.valueOf(v)

    @TypeConverter fun fromComplaintCategory(v: ComplaintCategory) = v.name
    @TypeConverter fun toComplaintCategory(v: String) = ComplaintCategory.valueOf(v)

    @TypeConverter fun fromComplaintStatus(v: ComplaintStatus) = v.name
    @TypeConverter fun toComplaintStatus(v: String) = ComplaintStatus.valueOf(v)

    @TypeConverter fun fromNotificationType(v: NotificationType) = v.name
    @TypeConverter fun toNotificationType(v: String) = NotificationType.valueOf(v)

    @TypeConverter fun fromStringList(v: List<String>) = v.joinToString(",")
    @TypeConverter fun toStringList(v: String): List<String> = if (v.isBlank()) emptyList() else v.split(",")
}
