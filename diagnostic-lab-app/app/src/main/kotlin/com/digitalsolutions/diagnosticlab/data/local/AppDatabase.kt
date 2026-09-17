package com.digitalsolutions.diagnosticlab.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import com.digitalsolutions.diagnosticlab.data.local.dao.*
import com.digitalsolutions.diagnosticlab.data.local.entities.*

@Database(
    entities = [
        UserEntity::class,
        PatientEntity::class,
        AddressEntity::class,
        LaboratoryEntity::class,
        InvestigationEntity::class,
        LaboratoryInvestigationEntity::class,
        PhlebotomistEntity::class,
        BookingEntity::class,
        BookingItemEntity::class,
        PaymentEntity::class,
        PhlebotomistAssignmentEntity::class,
        SampleEntity::class,
        SampleTrackingEventEntity::class,
        ReportEntity::class,
        MedicalRecordEntity::class,
        FeverRecordEntity::class,
        NotificationEntity::class,
        ComplaintEntity::class,
        AuditLogEntity::class
    ],
    version = 1,
    exportSchema = true
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun userDao(): UserDao
    abstract fun patientDao(): PatientDao
    abstract fun addressDao(): AddressDao
    abstract fun laboratoryDao(): LaboratoryDao
    abstract fun investigationDao(): InvestigationDao
    abstract fun laboratoryInvestigationDao(): LaboratoryInvestigationDao
    abstract fun phlebotomistDao(): PhlebotomistDao
    abstract fun bookingDao(): BookingDao
    abstract fun bookingItemDao(): BookingItemDao
    abstract fun paymentDao(): PaymentDao
    abstract fun phlebotomistAssignmentDao(): PhlebotomistAssignmentDao
    abstract fun sampleDao(): SampleDao
    abstract fun sampleTrackingEventDao(): SampleTrackingEventDao
    abstract fun reportDao(): ReportDao
    abstract fun medicalRecordDao(): MedicalRecordDao
    abstract fun feverRecordDao(): FeverRecordDao
    abstract fun notificationDao(): NotificationDao
    abstract fun complaintDao(): ComplaintDao
    abstract fun auditLogDao(): AuditLogDao

    companion object {
        @Volatile private var instance: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "diagnostic_lab.db"
                ).build().also { instance = it }
            }
    }
}
