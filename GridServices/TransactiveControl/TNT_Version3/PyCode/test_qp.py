import csv


def create_building_demand_curve():
    qp = list()
    import csv

    with open('/home/niddodi/Desktop/qp.csv', mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)

        for row in csv_reader:
            qp.append(dict(quantity=row['quantity'], price=row['price']))

    demand_curves = list()
    lenth = len(qp)/2
    print(lenth)
    for i in range(0, int(lenth)):
        curve = dict()
        curve['quantity'] = qp[i*2+1]['quantity']
        curve['price'] = qp[i*2+1]['price']
        # curve = PolyLine()
        # curve.add(Point(quantity=qp[i]['quantity'], price=qp[i]['price']))
        # curve.add(Point(quantity=qp[i + 1]['quantity'], price=qp[i + 1]['price']))
        demand_curves.append(curve)
        print(demand_curves)


if __name__ == '__main__':
    print("testing reading csv")
    create_building_demand_curve()
