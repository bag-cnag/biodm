# async def main():
#     await app.db.init_db()
#     # await test_entities()
#     # await test_2(proj)
    # await uvicorn.run(app)

async def test_entities():
    from uuid import uuid4

    ## entities
    # groups
    g0 = tables.Group(name="ADMIN")
    g1 = tables.Group(name="CNAG")
    g2 = tables.Group(name="CNAG_SC", name_parent=g1.name)
    g2.parent = g1
    g3 = tables.Group(name="EvilCorp")

    # schma test
    schema = schemas.GroupSchema()
    print(schema.dumps(obj=g0, indent=2))
    print(schema.dumps(obj=g2, indent=2))
    import json
    d = {
        "name": "CNAG_FG",
        "name_parent": "CNAG"
    }
    # g4 = schema.loads(json.dumps(d))
    g4 = schema.Meta.model(**schema.load(d))
    print(g4)
    print(g2)

    # admin
    u0 = tables.User(id=uuid4())
    u0.groups.append(g0)
    # normal user
    u1 = tables.User(id=uuid4())
    u1.groups.append(g2)

    # tags
    # tsvc = services.TagService(app=app)
    # tsch = schemas.TagSchema()
    # tctrl = TagController.init(app=app)

    tctrl = TagController.init(app=app)
    t1 = await tctrl.create(data=json.dumps(
        {"name": "cancer"}
    ))
    t2 = await tctrl.create(data=json.dumps(
        {"name": "genomics"}
    ))
    print(tctrl.routes())
    # t1 = await tsvc.create(
    #     tsch.loads(
    #         json_data=json.dumps({
    #             "name": "cancer"
    #         })
    #     )
    # )
    # t2 = await tsvc.create(
    #     tsch.loads(
    #         json_data=json.dumps({
    #             "name": "genomics"
    #         })
    #     )
    # )
    # x = await tsvc.read(name="cancer")
    # print("X:", x.id, " _ ", x.name)
    # t1 = tables.Tag(name="cancer")
    # t2 = tables.Tag(name="genomics")


    # dataset
    ds = tables.dataset.Dataset(
        name="th_exp1",
        name_group="CNAG_SC",
        id_user_contact=u0.id,
        tags=[t2]
    )

    # # project
    # p1 = orm.Project(
    #     name="TOTO",
    #     permission_level='2',
    #     id_user_principal_investigator=u0.id,
    #     id_user_updater=u1.id,
    #     id_user_responsible=u1.id,
    #     datasets=[
    #         orm.Dataset(
    #             name="th_exp1",
    #             specie="human",
    #             disease="asthma",
    #             treatment="codeine",
    #             genome_assembly="mm10",
    #             genome_annotation="GENCODE v39",
    #             sample_type="blood",
    #             sample_details="Collected on a full moon at 12a.m",
    #             sample_count=56,
    #             molecular_info="CITEseq",
    #             platform_name="Visium",
    #             platform_kit="10X v3",
    #             data_type="RNA-Seq",
    #             value_type="array",
    #             name_group="CNAG_SC",
    #             id_user_contact=u0.id,
    #             tags=[t2]
    #         ),
    #     ],
    #     groups=[g2],
    #     permission_lv2=orm.Permission_lv2(
    #         is_whitelist=False,
    #         groups=[g3]
    #     ),
    # )

    # Insert in db
    async with app.db.session() as db:
        db.add_all([
            g0, g1, g2, g3, g4,
            u0, u1,
            # t1, t2,
            # plv2,
            ds,
        ])

    ## Insert in db
    # async with AsyncSession(engine) as session:
    #     async with session.begin():
    #         session.add_all(
    #             [
    #                 g0, g1, g2, g3,
    #                 u1,
    #                 t1, t2,
    #                 # plv2,
    #                 p1,
    #             ]
    #         )

    #     await session.commit()

    # session = db.db()
    # with session.begin():
    #   session.add(t1)
    #   session.commit()  
    # session = await anext(db.db())
    # session.add(t1)
    # session.commit()
    #
    #  session.add_all([t1])
    # async with session.begin():
    #     session.add_all([
    #         t1
    #     ])
        # session.add_all([t1, t2, p1, apg1])
        # session.add_all([t1])
        # pass

    # stmt = 
    # await session.execute(stmt)

    # session.add(t1)
    # session.add(t2)
    # return p1
    # print(apg1.project)
    # print(p1.id)

# async def test_2(proj):
#     print(proj.id)