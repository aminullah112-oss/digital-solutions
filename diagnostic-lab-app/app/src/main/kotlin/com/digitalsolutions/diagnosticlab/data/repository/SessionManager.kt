package com.digitalsolutions.diagnosticlab.data.repository

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.digitalsolutions.diagnosticlab.domain.model.AppLanguage
import com.digitalsolutions.diagnosticlab.domain.model.Session
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.digitalsolutions.diagnosticlab.locale.LocaleHelper
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.sessionStore by preferencesDataStore(name = "session_prefs")

/** Holds "who is logged in" and app-wide settings like language. Backed by DataStore so it survives process death. */
class SessionManager(private val context: Context) {

    private object Keys {
        val USER_ID = stringPreferencesKey("user_id")
        val ROLE = stringPreferencesKey("role")
        val MOBILE = stringPreferencesKey("mobile")
        val LINKED_ENTITY_ID = stringPreferencesKey("linked_entity_id")
        val LANGUAGE = stringPreferencesKey("language")
        val ACTIVE_PATIENT_ID = stringPreferencesKey("active_patient_id")
    }

    val session: Flow<Session?> = context.sessionStore.data.map { prefs ->
        val userId = prefs[Keys.USER_ID] ?: return@map null
        val role = prefs[Keys.ROLE]?.let { runCatching { UserRole.valueOf(it) }.getOrNull() } ?: return@map null
        Session(userId, role, prefs[Keys.MOBILE].orEmpty(), prefs[Keys.LINKED_ENTITY_ID])
    }

    val language: Flow<String> = context.sessionStore.data.map { it[Keys.LANGUAGE] ?: AppLanguage.ENGLISH.tag }

    val activePatientId: Flow<String?> = context.sessionStore.data.map { it[Keys.ACTIVE_PATIENT_ID] }

    suspend fun signIn(userId: String, role: UserRole, mobile: String, linkedEntityId: String?) {
        context.sessionStore.edit { prefs ->
            prefs[Keys.USER_ID] = userId
            prefs[Keys.ROLE] = role.name
            prefs[Keys.MOBILE] = mobile
            if (linkedEntityId != null) prefs[Keys.LINKED_ENTITY_ID] = linkedEntityId else prefs.remove(Keys.LINKED_ENTITY_ID)
        }
    }

    suspend fun setActivePatient(patientId: String) {
        context.sessionStore.edit { it[Keys.ACTIVE_PATIENT_ID] = patientId }
    }

    suspend fun setLanguage(tag: String) {
        context.sessionStore.edit { it[Keys.LANGUAGE] = tag }
        LocaleHelper.persist(context, tag)
    }

    suspend fun signOut() {
        context.sessionStore.edit { it.clear() }
    }
}
