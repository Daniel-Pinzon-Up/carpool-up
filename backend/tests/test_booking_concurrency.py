"""Aceptaciones simultaneas con conexiones reales: el bloqueo del viaje evita la sobreventa.

A diferencia del resto de pruebas, esta confirma datos en carpool_test (cada aceptacion
corre en su propia conexion) y los borra al terminar.
"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.clock import local_today, utcnow
from app.core.enums import (
    BookingStatus,
    PlaceKind,
    ReviewStatus,
    Sex,
    UserRole,
    UserStatus,
    VehicleType,
)
from app.core.errors import AppError
from app.core.geo import point
from app.core.security import hash_password
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreate
from app.modules.bookings.service import BookingService
from app.modules.documents.models import DriverLicense
from app.modules.places.models import Place
from app.modules.trips.models import Trip
from app.modules.trips.schemas import TripCreate
from app.modules.trips.service import TripService
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from tests.conftest import FakeProvider

pytestmark = pytest.mark.integration

SEATS = 2
PASSENGERS = 6


def person(tag: str, n: int, role: UserRole) -> User:
    return User(
        email=f"concurrency-{tag}-{n}@unipamplona.edu.co",
        password_hash=hash_password("clave-de-prueba-123"),
        full_name=f"Concurrencia {n}",
        sex=Sex.FEMALE,
        role=role,
        status=UserStatus.ACTIVE,
    )


async def test_concurrent_accepts_never_overbook(engine: AsyncEngine) -> None:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:10]
    letters = "".join(chr(65 + int(c, 16)) for c in tag[:3])
    user_ids: list[uuid.UUID] = []
    place_ids: list[uuid.UUID] = []
    try:
        async with sessions() as session:
            driver = person(tag, 0, UserRole.DRIVER)
            passengers = [person(tag, n, UserRole.PASSENGER) for n in range(1, PASSENGERS + 1)]
            places = [
                Place(name="Campus prueba", kind=PlaceKind.CAMPUS, point=point(7.3870, -72.6495)),
                Place(
                    name="Terminal prueba", kind=PlaceKind.LANDMARK, point=point(7.3712, -72.6512)
                ),
            ]
            session.add_all([driver, *passengers, *places])
            await session.flush()
            user_ids = [driver.id, *(p.id for p in passengers)]
            place_ids = [p.id for p in places]
            session.add(
                DriverLicense(
                    user_id=driver.id,
                    file_path="licenses/x.pdf",
                    content_type="application/pdf",
                    expires_on=local_today() + timedelta(days=365),
                    status=ReviewStatus.APPROVED,
                )
            )
            vehicle = Vehicle(
                owner_id=driver.id,
                type=VehicleType.CAR,
                plate=f"{letters}{int(tag[3:6], 16) % 900 + 100}",
                brand="Renault",
                model="Logan",
                color="Blanco",
                year=2019,
                capacity=5,
            )
            session.add(vehicle)
            await session.commit()

            trip = await TripService(session, FakeProvider()).create(
                driver,
                TripCreate(
                    place_ids=place_ids,
                    departs_at=utcnow() + timedelta(days=2),
                    vehicle_id=vehicle.id,
                    seats=SEATS,
                    price_per_seat=1000,
                ),
            )
            bookings = BookingService(session)
            booking_ids = [
                (
                    await bookings.request(
                        p,
                        trip.id,
                        BookingCreate(pickup_place_id=place_ids[0], dropoff_place_id=place_ids[1]),
                    )
                ).id
                for p in passengers
            ]

        async def accept(booking_id: uuid.UUID) -> str:
            async with sessions() as session:
                owner = await session.get(User, user_ids[0])
                assert owner is not None
                try:
                    await BookingService(session).accept(owner, booking_id)
                except AppError as exc:
                    return exc.code
                return "accepted"

        results = await asyncio.gather(*(accept(b) for b in booking_ids))
        assert results.count("accepted") == SEATS
        assert results.count("TRIP_FULL") == PASSENGERS - SEATS

        async with sessions() as session:
            taken = await session.scalar(
                select(func.sum(Booking.seats)).where(
                    Booking.trip_id == trip.id, Booking.status == BookingStatus.ACCEPTED
                )
            )
            assert taken == SEATS
    finally:
        async with sessions() as session:
            if user_ids:
                await session.execute(delete(Trip).where(Trip.driver_id == user_ids[0]))
                await session.execute(delete(User).where(User.id.in_(user_ids)))
            if place_ids:
                await session.execute(delete(Place).where(Place.id.in_(place_ids)))
            await session.commit()
