import { initializeApp } from 'firebase/app'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  sendPasswordResetEmail,
  signOut,
  onAuthStateChanged,
} from 'firebase/auth'
import { getFirestore, doc, setDoc, getDoc } from 'firebase/firestore'

const firebaseConfig = {
  apiKey: 'AIzaSyBVkGH8-BrhPr1HWvlSCeTj40v7VqtZkW0',
  authDomain: 'sentinel-3d9b0.firebaseapp.com',
  projectId: 'sentinel-3d9b0',
  storageBucket: 'sentinel-3d9b0.firebasestorage.app',
  messagingSenderId: '317105589801',
  appId: '1:317105589801:web:9104b701ba6fa373f15638',
  measurementId: 'G-M0BJX5EJMQ',
}

const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
export const googleProvider = new GoogleAuthProvider()
export const db = getFirestore(app)

export {
  signInWithPopup,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  sendPasswordResetEmail,
  signOut,
  onAuthStateChanged,
  doc,
  setDoc,
  getDoc
}
